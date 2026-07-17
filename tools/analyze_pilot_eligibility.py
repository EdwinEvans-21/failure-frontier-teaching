"""Read-only protocol eligibility analysis for current or historical records."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot.eligibility import (
    ELIGIBILITY_POLICY,
    analyze_historical_eligibility,
)


def analyze_path(path: Path) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    return {
        "record_path": str(path.resolve()),
        "problem_id": record.get("problem_id"),
        **analyze_historical_eligibility(record),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", type=Path)
    group.add_argument("--run-dir", type=Path)
    args = parser.parse_args()

    if args.record is not None:
        paths = [args.record]
    else:
        paths = sorted((args.run_dir / "problems").glob("*/record.json"))
    result = {
        "analysis_policy": ELIGIBILITY_POLICY,
        "read_only": True,
        "record_count": len(paths),
        "records": [analyze_path(path) for path in paths],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
