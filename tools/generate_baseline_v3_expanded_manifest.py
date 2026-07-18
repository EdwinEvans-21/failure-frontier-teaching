from __future__ import annotations

import argparse
import json
from pathlib import Path

from baseline_v3_expanded import DEFAULT_MANIFEST, build_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = build_manifest(root, source_commit=args.source_commit)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Wrote {output} with {len(manifest['frozen_files'])} frozen files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
