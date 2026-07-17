"""Generate the Failure-Frontier benchmark baseline v2 manifest."""

from __future__ import annotations

from pathlib import Path
import argparse
import json

from baseline_v2 import DEFAULT_MANIFEST, build_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-commit")
    parser.add_argument("--verify-generators", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    verification = None
    if args.verify_generators:
        from verify_formal_test_generators import verify_generators
        verification = verify_generators(root)
        allowed = {"byte_identical", "not_applicable_no_generator"}
        if any(item["result"] not in allowed for item in verification["generators"]):
            raise RuntimeError("formal test regeneration did not match frozen tests")
    manifest = build_manifest(
        root,
        source_commit=args.source_commit,
        generator_verification=verification,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} with {len(manifest['frozen_files'])} frozen files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
