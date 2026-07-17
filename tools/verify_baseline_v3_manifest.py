"""Read-only verifier for the Failure-Frontier baseline v3."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from baseline_v3 import (
    BASELINE_ID,
    DEFAULT_MANIFEST,
    SCHEMA_VERSION,
    discover_frozen_paths,
    generator_records,
    hash_file,
    problem_records,
)


def verify(root: Path, manifest_path: Path) -> list[str]:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("baseline_id") != BASELINE_ID:
        errors.append("baseline_id mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")

    expected = {item["path"]: item for item in manifest.get("frozen_files", [])}
    if any(Path(path).name.lower() == "readme.md" for path in expected):
        errors.append("README.md entered the v3 frozen scope")
    current = set(discover_frozen_paths(root))
    for path in sorted(set(expected) - current):
        errors.append(f"missing frozen file: {path}")
    for path in sorted(current - set(expected)):
        errors.append(f"new frozen-scope file: {path}")
    for path in sorted(current & set(expected)):
        digest, mode = hash_file(root / path)
        if expected[path].get("hash_mode") != mode:
            errors.append(f"hash mode changed: {path}")
        if expected[path].get("sha256") != digest:
            errors.append(f"modified frozen file: {path}")

    summary = manifest.get("scope_summary", {})
    if summary.get("frozen_file_count") != len(expected):
        errors.append("frozen file count metadata mismatch")
    if summary.get("readme_frozen_count") != 0:
        errors.append("README frozen count must be zero")

    expected_problems = {
        item["fixture"]: item for item in manifest.get("problems", [])
    }
    current_problems = {item["fixture"]: item for item in problem_records(root)}
    fields = (
        "problem_id", "role", "entrypoint", "comparison", "checker",
        "time_limit_seconds", "memory_limit_mb", "public_test_count",
        "hidden_test_count", "pressure_test_count",
    )
    for fixture in sorted(expected_problems.keys() | current_problems.keys()):
        before = expected_problems.get(fixture)
        now = current_problems.get(fixture)
        if before is None or now is None:
            errors.append(f"problem set drift: {fixture}")
            continue
        for field in fields:
            if before.get(field) != now.get(field):
                errors.append(f"problem configuration drift: {fixture}.{field}")

    static_fields = ("fixture", "path", "deterministic", "random_seed", "check")
    expected_generators = [
        {field: item.get(field) for field in static_fields}
        for item in manifest.get("formal_test_generators", [])
    ]
    current_generators = [
        {field: item.get(field) for field in static_fields}
        for item in generator_records(root)
    ]
    if expected_generators != current_generators:
        errors.append("formal test generator determinism metadata drift")
    for item in manifest.get("formal_test_generators", []):
        if (
            item.get("path")
            and item.get("temporary_regeneration", {}).get("result")
            != "byte_identical"
        ):
            errors.append(
                "formal generator lacks byte-identical temporary verification: "
                + str(item.get("fixture"))
            )

    timing = manifest.get("judge_timing_policy", {})
    required_timing = {
        "runtime_source": "container_harness_monotonic_clock",
        "docker_startup_included": False,
        "docker_host_watchdog_verdict": "INTERNAL_ERROR",
        "submission_execution_timeout_verdict": "TIME_LIMIT_EXCEEDED",
    }
    for field, value in required_timing.items():
        if timing.get(field) != value:
            errors.append(f"judge timing policy drift: {field}")
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
        print(
            f"Baseline v3 verification could not run: {type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    if errors:
        print(
            f"Baseline v3 verification failed with {len(errors)} issue(s):",
            file=sys.stderr,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Baseline v3 verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
