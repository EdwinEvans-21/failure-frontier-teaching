"""Regenerate formal tests only in temporary directories and compare safely."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import argparse
import json
import subprocess
import sys

from generate_baseline_manifest import GENERATOR_BY_PROBLEM, PROBLEMS, canonical_json_bytes


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_generators(root: Path) -> dict[str, Any]:
    root = root.resolve()
    records = []
    for fixture, _ in PROBLEMS:
        generator = GENERATOR_BY_PROBLEM[fixture]
        if generator is None:
            records.append({
                "fixture": fixture,
                "result": "not_applicable_no_generator",
                "runs": 0,
                "files": [],
            })
            continue

        with TemporaryDirectory(prefix=f"ffbaseline-{fixture}-") as directory:
            temporary_root = Path(directory)
            outputs = [temporary_root / "run_1", temporary_root / "run_2"]
            failed = None
            for output in outputs:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(root / generator),
                        "--output-dir",
                        str(output),
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                if completed.returncode != 0:
                    failed = f"generator_exit_{completed.returncode}"
                    break
            if failed:
                records.append({
                    "fixture": fixture,
                    "result": failed,
                    "runs": len(outputs),
                    "files": [],
                })
                continue

            comparisons = []
            all_raw = True
            all_canonical = True
            frozen_root = root / "examples" / fixture
            for filename in ("public_tests.json", "hidden_tests.json"):
                frozen = frozen_root / filename
                generated = [output / filename for output in outputs]
                raw_equal = all(
                    candidate.read_bytes() == frozen.read_bytes()
                    for candidate in generated
                ) and generated[0].read_bytes() == generated[1].read_bytes()
                canonical_equal = all(
                    canonical_json_bytes(candidate) == canonical_json_bytes(frozen)
                    for candidate in generated
                ) and canonical_json_bytes(generated[0]) == canonical_json_bytes(generated[1])
                all_raw = all_raw and raw_equal
                all_canonical = all_canonical and canonical_equal
                comparisons.append({
                    "path": f"examples/{fixture}/{filename}",
                    "frozen_raw_sha256": _digest(frozen),
                    "generated_raw_sha256": _digest(generated[0]),
                    "raw_byte_identical": raw_equal,
                    "canonical_json_identical": canonical_equal,
                })
            result = (
                "byte_identical" if all_raw
                else "canonical_json_identical" if all_canonical
                else "mismatch"
            )
            records.append({
                "fixture": fixture,
                "result": result,
                "runs": 2,
                "files": comparisons,
            })
    return {
        "mode": "two_independent_temporary_directories",
        "comparison": "raw_bytes_and_canonical_json",
        "generators": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    report = verify_generators(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(
        record["result"] in {"byte_identical", "not_applicable_no_generator"}
        for record in report["generators"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
