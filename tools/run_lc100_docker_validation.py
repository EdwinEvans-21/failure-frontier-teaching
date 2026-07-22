from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import statistics
import sys
import time
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
# This validator must exercise the judge implementation in this checkout rather
# than an editable ffjudge install from a sibling experiment worktree.
sys.path = [entry for entry in sys.path if Path(entry).resolve() != SOURCE_ROOT]
sys.path.insert(0, str(SOURCE_ROOT))

from ffjudge.models import Verdict
from ffjudge.runner import DockerJudge

CANARY_ZIP = Path(r"C:\Users\Edaglem\Downloads\lc100_natural_bruteforce_canaries_v1.zip")
EXAMPLES = ROOT / "examples"
EXTRA_EXCLUDED = {"lc-0761-special-binary-string", "exact_monotone_paths"}
LC1489 = "lc-1489-find-critical-and-pseudo-critical-edges-in-minimum-spanning-tree"


@dataclass(frozen=True)
class Trial:
    verdict: str
    runtime_ms: int
    memory_peak_bytes: int | None = None
    case_id: str | None = None


def canary_targets() -> list[str]:
    with zipfile.ZipFile(CANARY_ZIP) as zf:
        names = sorted({
            Path(name).parts[2]
            for name in zf.namelist()
            if name.endswith("complexity_canary.py")
        })
    targets = {name for name in names if name not in EXTRA_EXCLUDED}
    if not (EXAMPLES / LC1489 / "complexity_canary.py").is_file():
        raise FileNotFoundError("lc-1489 complexity canary addon has not been merged")
    targets.add(LC1489)
    return sorted(targets)


def load_cases(directory: Path, filename: str) -> list[dict[str, Any]]:
    return json.loads((directory / filename).read_text(encoding="utf-8"))


def select_max_stress_case(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        raise ValueError("stress_tests.json must not be empty")
    designated = [
        case for case in cases if case.get("is_complexity_canary_stress") is True
    ]
    if len(designated) > 1:
        raise ValueError("at most one stress case may be designated for the complexity canary")
    if designated:
        return designated[0]
    return max(
        cases,
        key=lambda case: len(json.dumps(case.get("args", []), sort_keys=True, ensure_ascii=False))
        + len(json.dumps(case.get("kwargs", {}), sort_keys=True, ensure_ascii=False)),
    )


def run_case(judge: DockerJudge, submission: Path, problem: Path, case: dict[str, Any], *, phase: str) -> Trial:
    tests = problem.parent / "_single_case.json"
    tests.write_text(json.dumps([case], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        result = judge.judge(submission, problem, tests, phase=phase)
        return Trial(
            verdict=result.verdict.name,
            runtime_ms=result.runtime_ms,
            memory_peak_bytes=result.memory_peak_bytes,
            case_id=case.get("case_id"),
        )
    finally:
        if tests.exists():
            tests.unlink()


def p95(values: list[int]) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[index]


def summarize_runtimes(values: list[int]) -> dict[str, int | float]:
    return {
        "runs": len(values),
        "median_ms": int(statistics.median(values)),
        "p95_ms": int(p95(values)),
        "max_ms": int(max(values)),
    }


def provisional_time_limit_seconds(summary: dict[str, int | float]) -> float:
    """Return a deliberately conservative, unenforced first-pass time limit."""
    protected_ms = max(
        1_000,
        5 * int(summary["p95_ms"]),
        4 * int(summary["max_ms"]),
    )
    return math.ceil(protected_ms / 250) * 0.25


def provisional_memory_limit_mb(memory_peaks: list[int]) -> int:
    if not memory_peaks:
        raise ValueError("reference memory peak is unavailable")
    observed_mb = max(memory_peaks) / (1024 * 1024)
    protected_mb = max(128, math.ceil(observed_mb * 3))
    return int(math.ceil(protected_mb / 16) * 16)


def validate_problem(
    judge: DockerJudge,
    root: Path,
    problem_id: str,
    *,
    warmups: int,
    measurements: int,
    reference_only: bool = False,
) -> dict[str, Any]:
    directory = root / "examples" / problem_id
    problem = directory / "problem.json"
    accepted = directory / "accepted.py"
    public = load_cases(directory, "public_tests.json")
    hidden = load_cases(directory, "hidden_tests.json")
    stress = load_cases(directory, "stress_tests.json")
    max_case = select_max_stress_case(stress)

    ref_public = [judge.judge(accepted, problem, directory / "public_tests.json", phase="public")]
    ref_hidden = [judge.judge(accepted, problem, directory / "hidden_tests.json", phase="hidden")]
    ref_stress = judge.judge(accepted, problem, directory / "stress_tests.json", phase="hidden")
    if ref_public[0].verdict != Verdict.ACCEPTED or ref_hidden[0].verdict != Verdict.ACCEPTED or ref_stress.verdict != Verdict.ACCEPTED:
        raise AssertionError(f"reference failed on {problem_id}")

    benchmark_runtimes: list[int] = []
    benchmark_memory_peaks: list[int] = []
    max_case_result = None
    for _ in range(warmups + measurements):
        trial = run_case(judge, accepted, problem, max_case, phase="hidden")
        if trial.verdict != Verdict.ACCEPTED.name:
            raise AssertionError(f"reference not stable on max stress for {problem_id}: {trial.verdict}")
        benchmark_runtimes.append(trial.runtime_ms)
        if trial.memory_peak_bytes is None:
            raise AssertionError(
                f"reference memory peak unavailable on max stress for {problem_id}"
            )
        benchmark_memory_peaks.append(trial.memory_peak_bytes)
        max_case_result = trial

    runtime_summary = summarize_runtimes(benchmark_runtimes[warmups:])
    configured_limits = json.loads(problem.read_text(encoding="utf-8"))["limits"]
    result: dict[str, Any] = {
        "problem_id": problem_id,
        "public_verdict": ref_public[0].verdict.name,
        "hidden_verdict": ref_hidden[0].verdict.name,
        "stress_verdict": ref_stress.verdict.name,
        "public_case_count": len(public),
        "hidden_case_count": len(hidden),
        "stress_case_count": len(stress),
        "max_stress_case_id": max_case.get("case_id"),
        "max_stress_case_args_digest": len(json.dumps(max_case.get("args", []), sort_keys=True, ensure_ascii=False)),
        "reference_runtimes_ms": benchmark_runtimes,
        "reference_runtime_summary": runtime_summary,
        "reference_warmup_count": warmups,
        "reference_measurement_count": measurements,
        "runtime_measurement_scope": (
            "container harness: starts immediately before submission import and "
            "entrypoint resolution; excludes Docker image build, container creation, "
            "and container startup"
        ),
        "provisional_time_limit": {
            "status": "reference_only_not_enforced",
            "formula": "ceil_to_0.25s(max(1.0s, 5*p95, 4*max))",
            "suggested_seconds": provisional_time_limit_seconds(runtime_summary),
            "current_configured_seconds": configured_limits["time_seconds"],
        },
        "reference_memory_peaks_bytes": benchmark_memory_peaks,
        "reference_memory_peak_summary": {
            "runs": len(benchmark_memory_peaks[warmups:]),
            "median_mb": round(
                statistics.median(benchmark_memory_peaks[warmups:]) / (1024 * 1024),
                3,
            ),
            "max_mb": round(
                max(benchmark_memory_peaks[warmups:]) / (1024 * 1024), 3
            ),
        },
        "provisional_memory_limit": {
            "status": "reference_only_not_enforced",
            "formula": "ceil_to_16MiB(max(128MiB, 3*observed_peak))",
            "suggested_mb": provisional_memory_limit_mb(
                benchmark_memory_peaks[warmups:]
            ),
            "current_configured_mb": configured_limits["memory_mb"],
        },
        "memory_peak_mb": round(
            max(benchmark_memory_peaks[warmups:]) / (1024 * 1024), 3
        ),
        "memory_peak_status": "cgroup_peak_from_container_harness",
    }
    if reference_only:
        result["canary_validation"] = "skipped_reference_only"
        return result

    canary = directory / "complexity_canary.py"
    canary_small = {
        "public": judge.judge(
            canary, problem, directory / "public_tests.json", phase="public"
        ).verdict,
    }
    if canary_small["public"] != Verdict.ACCEPTED:
        raise AssertionError(f"canary failed on small inputs for {problem_id}")
    canary_results = [
        run_case(judge, canary, problem, max_case, phase="hidden")
        for _ in range(3)
    ]
    resource_verdicts = {
        Verdict.TIME_LIMIT_EXCEEDED.name,
        Verdict.MEMORY_LIMIT_EXCEEDED.name,
    }
    observed_verdicts = [item.verdict for item in canary_results]
    if (
        not all(verdict in resource_verdicts for verdict in observed_verdicts)
        or len(set(observed_verdicts)) != 1
    ):
        observed = ", ".join(item.verdict for item in canary_results)
        raise AssertionError(
            "canary did not stably reach one resource limit on max stress for "
            f"{problem_id}: {observed}"
        )
    result.update({
        "canary_small_verdicts": {
            key: value.name if hasattr(value, "name") else str(value)
            for key, value in canary_small.items()
        },
        "canary_max_stress_verdicts": [item.verdict for item in canary_results],
        "canary_max_stress_resource_failure": observed_verdicts[0],
        "canary_max_stress_case_id": max_case_result.case_id if max_case_result else None,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "experiments" / "problem_bank_v4_100" / "lc100_docker_validation.json")
    parser.add_argument("--report", type=Path, default=ROOT / "experiments" / "problem_bank_v4_100" / "lc100_docker_validation.md")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--measurements", type=int, default=7)
    parser.add_argument(
        "--problem-id",
        action="append",
        default=[],
        help="Validate only the named problem. Repeatable; intended for repairing a failed quality gate.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore already completed rows in an existing output file.",
    )
    parser.add_argument(
        "--error-log",
        type=Path,
        default=None,
        help="JSONL file receiving one safe per-problem failure record.",
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Skip canaries and produce unenforced first-pass reference time limits.",
    )
    args = parser.parse_args()

    judge = DockerJudge()
    judge.build_image(ROOT)
    problems = canary_targets()
    if args.problem_id:
        requested = set(args.problem_id)
        unknown = requested.difference(problems)
        if unknown:
            parser.error(f"unknown target problem(s): {', '.join(sorted(unknown))}")
        problems = [problem_id for problem_id in problems if problem_id in requested]
    if args.error_log is None:
        args.error_log = args.output.with_name(args.output.stem + ".errors.jsonl")

    rows: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    failures: list[dict[str, str]] = []
    if args.output.exists() and not args.no_resume:
        try:
            prior = json.loads(args.output.read_text(encoding="utf-8"))
            rows = list(prior.get("problems", []))
            completed_ids = {row["problem_id"] for row in rows}
        except (OSError, ValueError, TypeError, KeyError):
            rows = []
            completed_ids = set()

    def write_progress() -> None:
        attempted_ids = completed_ids | {
            failure["problem_id"] for failure in failures
        }
        payload = {
            "schema_version": "1.2",
            "target_problem_count": len(problems),
            "completed_problem_count": len(rows),
            "attempted_problem_count": len(attempted_ids),
            "completed": len(attempted_ids) == len(problems),
            "ready_for_freeze": (
                not args.reference_only
                and len(attempted_ids) == len(problems)
                and not failures
            ),
            "calibration_mode": "reference_only" if args.reference_only else "full",
            "excluded_problem_ids": sorted(EXTRA_EXCLUDED),
            "problems": rows,
            "validation_failures": failures,
            "memory_peak_mb": None,
            "memory_peak_status": "unavailable_from_current_dockerjudge",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    for index, problem_id in enumerate(problems, 1):
        if problem_id in completed_ids:
            print(f"[{index}/{len(problems)}] already validated {problem_id}", flush=True)
            continue
        print(f"[{index}/{len(problems)}] validating {problem_id}", flush=True)
        try:
            rows.append(
                validate_problem(
                    judge, ROOT, problem_id,
                    warmups=args.warmups, measurements=args.measurements,
                    reference_only=args.reference_only,
                )
            )
            completed_ids.add(problem_id)
        except Exception as error:
            failure = {
                "problem_id": problem_id,
                "error_type": type(error).__name__,
                "message": str(error),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            failures.append(failure)
            args.error_log.parent.mkdir(parents=True, exist_ok=True)
            with args.error_log.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
            print(
                f"[{index}/{len(problems)}] FAILED {problem_id}: "
                f"{failure['error_type']}",
                flush=True,
            )
            write_progress()
            continue
        write_progress()

    report = {
        "schema_version": "1.2",
        "target_problem_count": len(problems),
        "completed_problem_count": len(rows),
        "attempted_problem_count": len(rows) + len(failures),
        "completed": len(rows) + len(failures) == len(problems),
        "ready_for_freeze": (
            not args.reference_only and not failures and len(rows) == len(problems)
        ),
        "calibration_mode": "reference_only" if args.reference_only else "full",
        "excluded_problem_ids": sorted(EXTRA_EXCLUDED),
        "problems": rows,
        "validation_failures": failures,
        "error_log": str(args.error_log),
        "memory_peak_mb": None,
        "memory_peak_status": "unavailable_from_current_dockerjudge",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    summary_lines = [
        "# LC100 Docker Validation",
        "",
        f"- validated problems: {len(rows)}",
        f"- validation failures: {len(failures)}",
        f"- error log: {args.error_log}",
        f"- excluded_problem_ids: {', '.join(sorted(EXTRA_EXCLUDED))}",
        f"- warmups per problem: {args.warmups}",
        f"- measurements per problem: {args.measurements}",
        f"- calibration mode: {'reference-only' if args.reference_only else 'full'}",
        "- suggested time formula: ceil_to_0.25s(max(1.0s, 5*p95, 4*max))",
        "- peak memory: unavailable from current DockerJudge API",
        "",
        "## Status",
        "",
        (
            "REFERENCE_LIMITS_DRAFT"
            if args.reference_only and len(rows) == len(problems) and not failures
            else ("READY" if len(rows) == len(problems) and not failures else "NOT_READY")
        ),
    ]
    args.report.write_text("\n".join(summary_lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"validated": len(rows), "output": str(args.output), "report": str(args.report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
