from __future__ import annotations
import argparse, json
from pathlib import Path
from baseline_v4_100 import DEFAULT_MANIFEST, build_manifest
parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(__file__).parents[1]); parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
args = parser.parse_args(); root = args.root.resolve(); output = args.output if args.output.is_absolute() else root / args.output
output.parent.mkdir(parents=True, exist_ok=True); manifest = build_manifest(root)
output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {output} with {len(manifest['frozen_files'])} files and {manifest['problem_count']} problems.")
