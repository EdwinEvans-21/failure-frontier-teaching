"""Read-only verifier for a Failure-Frontier baseline manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import sys

from generate_baseline_manifest import (
    BASELINE_ID,
    SCHEMA_VERSION,
    discover_frozen_paths,
    hash_file,
    inspect_generator_records,
    read_problem_records,
)


DEFAULT_MANIFEST = Path("experiments/baseline_v1/baseline_manifest.json")


def verify(root: Path, manifest_path: Path) -> list[str]:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("baseline_id") != BASELINE_ID:
        errors.append("baseline_id mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")

    expected_files = {
        record["path"]: record for record in manifest.get("frozen_files", [])
    }
    current_paths = set(discover_frozen_paths(root))
    expected_paths = set(expected_files)
    for path in sorted(expected_paths - current_paths):
        errors.append(f"missing frozen file: {path}")
    for path in sorted(current_paths - expected_paths):
        errors.append(f"new frozen-scope file: {path}")
    for path in sorted(expected_paths & current_paths):
        actual_hash, actual_mode = hash_file(root / path)
        expected = expected_files[path]
        if actual_mode != expected.get("hash_mode"):
            errors.append(f"hash mode changed: {path}")
        if actual_hash != expected.get("sha256"):
            errors.append(
                f"modified frozen file: {path} "
                f"expected_sha256={expected.get('sha256')} actual_sha256={actual_hash}"
            )

    expected_problems = {
        record["fixture"]: record for record in manifest.get("problems", [])
    }
    current_problems = {
        record["fixture"]: record for record in read_problem_records(root)
    }
    config_fields = (
        "problem_id",
        "role",
        "entrypoint",
        "comparison",
        "time_limit_seconds",
        "memory_limit_mb",
        "public_test_count",
        "hidden_test_count",
        "pressure_test_count",
    )
    for fixture in sorted(expected_problems.keys() | current_problems.keys()):
        expected = expected_problems.get(fixture)
        current = current_problems.get(fixture)
        if expected is None or current is None:
            errors.append(f"problem set drift: {fixture}")
            continue
        for field in config_fields:
            if expected.get(field) != current.get(field):
                errors.append(f"problem configuration drift: {fixture}.{field}")

    expected_generators = manifest.get("formal_test_generators", [])
    current_generators = inspect_generator_records(root)
    static_fields = ("fixture", "path", "deterministic", "random_seed", "check")
    expected_static = [
        {field: record.get(field) for field in static_fields}
        for record in expected_generators
    ]
    if expected_static != current_generators:
        errors.append("formal test generator determinism metadata drift")
    for record in expected_generators:
        regeneration = record.get("temporary_regeneration", {})
        if record.get("path") and regeneration.get("result") != "byte_identical":
            errors.append(
                f"formal generator lacks byte-identical temporary verification: "
                f"{record.get('fixture')}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    try:
        errors = verify(root, manifest)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Baseline verification could not run: {type(error).__name__}", file=sys.stderr)
        return 2
    if errors:
        print(f"Baseline verification failed with {len(errors)} issue(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Baseline verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
