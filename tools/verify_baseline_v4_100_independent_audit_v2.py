from __future__ import annotations
import argparse, json
from pathlib import Path
from baseline_v4_100_independent_audit_v2 import BASELINE_ID, DEFAULT_MANIFEST, SCHEMA_VERSION, discover_frozen_paths, hash_file, problem_records

parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,default=Path(__file__).parents[1]); parser.add_argument("--manifest",type=Path,default=DEFAULT_MANIFEST)
args=parser.parse_args(); root=args.root.resolve(); path=args.manifest if args.manifest.is_absolute() else root/args.manifest
manifest=json.loads(path.read_text(encoding="utf-8")); errors=[]
if manifest.get("baseline_id")!=BASELINE_ID: errors.append("baseline_id mismatch")
if manifest.get("schema_version")!=SCHEMA_VERSION: errors.append("schema_version mismatch")
expected={row["path"]:row for row in manifest.get("frozen_files",[])}; current=set(discover_frozen_paths(root))
for item in sorted(set(expected)-current): errors.append(f"missing frozen file: {item}")
for item in sorted(current-set(expected)): errors.append(f"new frozen-scope file: {item}")
for item in sorted(current & set(expected)):
    digest,mode=hash_file(root/item)
    if digest!=expected[item].get("sha256") or mode!=expected[item].get("hash_mode"): errors.append(f"modified frozen file: {item}")
if manifest.get("problems")!=problem_records(root): errors.append("problem configuration drift")
if manifest.get("scope_summary",{}).get("readme_frozen_count")!=0: errors.append("README entered frozen scope")
if errors:
    print(f"Baseline verification failed with {len(errors)} issue(s):"); [print(f"- {item}") for item in errors]; raise SystemExit(1)
print("Independent-audit v2 100-problem snapshot verification passed.")
