from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).parents[1]
SOURCE_ROOT = ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from experiments.iterative.fresh_runner import (
    FreshTeacherLineageRunner, load_fresh_teacher_config,
)
from experiments.iterative.transport import SanitizedTransportTracker, TrackedModelClient
from experiments.pilot.config import load_config
from experiments.pilot.model_client import DeepSeekCompatibleClient
from ffjudge.runner import DockerJudge
from ffjudge.oracle_hardened.policy_judge import OracleHardenedPolicyJudge


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=("dry-run", "live"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--judge-policy", choices=("legacy", "oracle-hardened-v3"),
                        default="legacy")
    args = parser.parse_args()
    config = load_fresh_teacher_config(args.config)
    if args.mode:
        config = replace(config, mode=args.mode)
    if args.output_root:
        config = replace(config, output_root=str(Path(args.output_root).resolve()))
    root = ROOT
    if config.mode == "dry-run":
        policy = ("judge_v3_oracle_hardened_mixed31_v1"
                  if args.judge_policy == "oracle-hardened-v3"
                  else "legacy_ffjudge_v1")
        result = FreshTeacherLineageRunner(
            config, project_root=root, judge_policy=policy).dry_run(args.run_id)
    else:
        output = Path(config.output_root).resolve()
        if output == root or output.is_relative_to(root):
            raise SystemExit("live output must be outside the repository")
        base = load_config(root / config.base_pilot_config)
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}",
             base.execution.judge_image], capture_output=True, text=True,
            check=False)
        if inspected.returncode or not inspected.stdout.strip():
            raise SystemExit("cannot freeze Judge image")
        run_dir = output / args.run_id
        tracker = SanitizedTransportTracker(run_dir / "api_transport_attempts.jsonl")
        model = TrackedModelClient(
            DeepSeekCompatibleClient(base.model, opener=tracker), tracker)
        judge = (OracleHardenedPolicyJudge(base.execution.judge_image)
                 if args.judge_policy == "oracle-hardened-v3"
                 else DockerJudge(base.execution.judge_image))
        result = FreshTeacherLineageRunner(
            config, project_root=root, model=model,
            judge=judge,
            image_id=inspected.stdout.strip(),
            judge_policy=getattr(judge, "policy_version", "legacy_ffjudge_v1"),
        ).run(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
