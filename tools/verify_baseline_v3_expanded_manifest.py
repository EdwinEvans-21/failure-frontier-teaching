from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from baseline_v2 import hash_file
from baseline_v3_expanded import (
    BASELINE_ID,
    DEFAULT_MANIFEST,
    SCHEMA_VERSION,
    discover_frozen_paths,
    expanded_problem_records,
    verify_expanded_generator,
)


def verify(root: Path, manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    if manifest.get("baseline_id") != BASELINE_ID:
        errors.append("baseline_id mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    expected = {item["path"]: item for item in manifest.get("frozen_files", [])}
    current = set(discover_frozen_paths(root))
    if any(Path(path).name.lower() == "readme.md" for path in expected):
        errors.append("README entered expanded frozen scope")
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
    expected_problems = {item["fixture"]: item for item in manifest.get("problems", [])}
    for current_problem in expanded_problem_records(root):
        fixture = current_problem["fixture"]
        before = expected_problems.get(fixture)
        if before is None:
            errors.append(f"problem set drift: {fixture}")
            continue
        for field in (
            "problem_id", "role", "entrypoint", "comparison", "checker",
            "time_limit_seconds", "memory_limit_mb", "public_test_count",
            "hidden_test_count", "pressure_test_count", "topic",
            "memorization_risk",
        ):
            if before.get(field) != current_problem.get(field):
                errors.append(f"problem configuration drift: {fixture}.{field}")
    proof = verify_expanded_generator(root)
    if proof.get("result") != "normalized_text_identical":
        errors.append("expanded formal generator is not line-ending-normalized identical")
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
        print(f"Expanded baseline verification could not run: {type(error).__name__}",
              file=sys.stderr)
        return 2
    if errors:
        print(f"Expanded baseline verification failed with {len(errors)} issue(s):",
              file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Expanded baseline verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
