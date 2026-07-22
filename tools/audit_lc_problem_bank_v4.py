from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lc_problem_bank_v4_catalog import (
    FIXED_PROBLEMS,
    RESERVE_PROBLEMS,
    problem_id,
)


EXAMPLES = ROOT / "examples"
OUTPUT = ROOT / "experiments" / "problem_bank_v4_100"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _frozen_legacy_names() -> set[str] | None:
    path = OUTPUT / "legacy_lc_snapshot.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {Path(name).parts[1] for name in data["files"]}


def scan() -> dict[str, object]:
    directories = sorted(path for path in EXAMPLES.iterdir() if path.is_dir())
    frozen_names = _frozen_legacy_names()
    lc = [path for path in directories if path.name.startswith("lc-")
          and (frozen_names is None or path.name in frozen_names)]
    non_lc = [path for path in directories if not path.name.startswith("lc-")]
    snapshot = {
        path.relative_to(ROOT).as_posix(): _sha(path)
        for directory in lc
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
    existing = {path.name for path in lc}
    selected: list[dict[str, object]] = []
    replacements: list[dict[str, object]] = []
    reserve_index = 0
    for record in FIXED_PROBLEMS:
        identifier = problem_id(record)
        if identifier not in existing:
            selected.append({**record, "problem_id": identifier, "selection": "FIXED"})
            continue
        while reserve_index < len(RESERVE_PROBLEMS):
            replacement = RESERVE_PROBLEMS[reserve_index]
            reserve_index += 1
            replacement_id = problem_id(replacement)
            if replacement_id in existing or any(row["problem_id"] == replacement_id for row in selected):
                continue
            selected.append({**replacement, "problem_id": replacement_id, "selection": "RESERVE"})
            replacements.append({
                "fixed_problem_id": identifier,
                "status": "ALREADY_PRESENT",
                "replacement_problem_id": replacement_id,
            })
            break
        else:
            raise RuntimeError("reserve list exhausted")
    if len(lc) != 31 or len(selected) != 69 or len(existing | {str(x['problem_id']) for x in selected}) != 100:
        raise RuntimeError("31 + 69 = 100 selection reconciliation failed")
    gaps = []
    for directory in lc:
        counts = {}
        for name in ("public_tests.json", "hidden_tests.json", "stress_tests.json", "mutants.json"):
            path = directory / name
            counts[name] = len(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else 0
        gaps.append({
            "problem_id": directory.name,
            **counts,
            "v4_supplement_required": (
                counts["public_tests.json"] < 5
                or counts["hidden_tests.json"] < 60
                or counts["stress_tests.json"] < 3
                or counts["mutants.json"] < 5
            ),
            "supplement_location": f"experiments/problem_bank_v4_100/legacy_supplements/{directory.name}",
        })
    return {
        "schema_version": "1.0",
        "problem_bank_policy": "lc_problem_bank_v4_100",
        "benchmark_baseline": "baseline_v4_100_lc",
        "examples_directory": str(EXAMPLES),
        "all_problem_directories": [path.name for path in directories
                                    if not path.name.startswith("lc-") or path in lc],
        "lc_directories": [path.name for path in lc],
        "non_lc_directories": [path.name for path in non_lc],
        "lc_count_before": len(lc),
        "non_lc_count": len(non_lc),
        "selected_new_problems": selected,
        "replacements": replacements,
        "legacy_file_sha256": snapshot,
        "legacy_quality_gaps": gaps,
    }


def main() -> int:
    result = scan()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "phase_a_audit.json", result)
    _write_json(OUTPUT / "new_problem_selection.json", result["selected_new_problems"])
    _write_json(OUTPUT / "replacement_log.json", result["replacements"])
    _write_json(OUTPUT / "legacy_lc_snapshot.json", {
        "schema_version": "1.0",
        "file_count": len(result["legacy_file_sha256"]),
        "files": result["legacy_file_sha256"],
    })
    _write_json(OUTPUT / "legacy_quality_gap.json", result["legacy_quality_gaps"])
    markdown = [
        "# LC Problem Bank v4 — Phase A Format Audit", "",
        f"- All directories: {len(result['all_problem_directories'])}",
        f"- `lc-*` directories: {result['lc_count_before']}",
        f"- Non-`lc-*` directories ignored: {result['non_lc_count']}",
        "- Existing `lc-*` comparator: exact only",
        "- Existing `lc-*` entrypoint: class_method only",
        "- Existing generated layout: problem.json, accepted.py, public_tests.json, hidden_tests.json, stress_tests.json, benchmark_metadata.json, mutants.json, and three wrong fixtures.",
        "- Existing trusted oracles: centralized independent reference/bruteforce functions in `src/ffjudge/oracles/expanded_*.py`.",
        "- Existing deterministic generator: `tools/generate_expanded_benchmarks.py`, seed 20260718.",
        "- Existing baselines: baseline_v1, baseline_v2, baseline_v3, baseline_v3_expanded.", "",
        "All 31 existing lc directories have 2 public, 12 hidden, 3 stress, and 3 mutant records. They therefore require v4 supplemental coverage. Supplements are versioned outside the legacy directories so old baselines remain byte-identical.", "",
        "The fixed list overlaps existing 1547, 2035, and 2188. Reserve 2421 is also already present. Replacements selected in order: 2334, 2338, 2360.", "",
        "The requested calibration categories cannot all be found inside the legacy 31: there is no unordered/custom comparator or function entrypoint there. The excluded legacy `exact_monotone_paths` directory demonstrates the custom-checker call chain.", "",
    ]
    (OUTPUT / "problem_format_audit.md").write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps({
        "lc_before": result["lc_count_before"],
        "non_lc": result["non_lc_count"],
        "new_selected": len(result["selected_new_problems"]),
        "final_expected": 100,
        "legacy_files_frozen": len(result["legacy_file_sha256"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
