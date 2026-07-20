from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.ffjudge.oracle_hardened.replay import run


def main() -> int:
    parser=argparse.ArgumentParser(description="Oracle-hardened observed-submission replay; never calls a model API.")
    parser.add_argument("--source-run",type=Path,required=True)
    parser.add_argument("--output-root",type=Path,required=True)
    parser.add_argument("--mode",choices=("dry-run","calibration","full","resume"),required=True)
    parser.add_argument("--image",default="ffjudge-python:latest")
    args=parser.parse_args()
    result=run(repo=ROOT,source=args.source_run,output=args.output_root,mode=args.mode,image=args.image)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
