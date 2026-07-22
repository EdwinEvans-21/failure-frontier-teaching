from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = report.get("problems")
    failures = report.get("validation_failures")
    target = report.get("target_problem_count")
    if report.get("calibration_mode") != "reference_only":
        raise ValueError("threshold report is not a reference-only calibration")
    if not report.get("completed") or not isinstance(rows, list):
        raise ValueError("reference-only calibration has not completed")
    if not isinstance(target, int) or len(rows) != target:
        raise ValueError("reference-only calibration has incomplete problem rows")
    if failures:
        raise ValueError("reference-only calibration has validation failures")
    return report


def validated_limits(row: dict[str, Any]) -> tuple[float, int]:
    if not all(
        row.get(key) == "ACCEPTED"
        for key in ("public_verdict", "hidden_verdict", "stress_verdict")
    ):
        raise ValueError(f"{row.get('problem_id')}: reference did not pass all suites")
    time_limit = row.get("provisional_time_limit", {}).get("suggested_seconds")
    memory_limit = row.get("provisional_memory_limit", {}).get("suggested_mb")
    if (
        not isinstance(time_limit, (int, float))
        or time_limit <= 0
        or not isinstance(memory_limit, int)
        or memory_limit <= 0
    ):
        raise ValueError(f"{row.get('problem_id')}: missing calibrated limits")
    return float(time_limit), memory_limit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply only a completed reference-only v1 limit calibration."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--audit-output",
        type=Path,
        default=ROOT / "experiments" / "problem_bank_v4_100"
        / "reference_thresholds_v1_applied.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = load_report(args.report)
    applied: list[dict[str, Any]] = []
    for row in report["problems"]:
        problem_id = row["problem_id"]
        time_seconds, memory_mb = validated_limits(row)
        path = ROOT / "examples" / problem_id / "problem.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        previous = dict(data["limits"])
        updated = dict(previous)
        updated["time_seconds"] = time_seconds
        updated["memory_mb"] = memory_mb
        applied.append(
            {
                "problem_id": problem_id,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "previous_limits": previous,
                "v1_reference_only_limits": updated,
            }
        )
        if not args.dry_run:
            data["limits"] = updated
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    audit = {
        "schema_version": "1.0",
        "source_report": str(args.report),
        "mode": "reference_only_v1",
        "applied": not args.dry_run,
        "problem_count": len(applied),
        "limits": applied,
    }
    if not args.dry_run:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({"problems": len(applied), "applied": not args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
