from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import subprocess

from experiments.iterative.config import FLAT_V2_CONDITION, load_iterative_config
from experiments.iterative.fakes import (
    DeterministicFakeJudge, DeterministicFlatPipeline,
    DeterministicStructuredFlatPipeline,
)
from experiments.iterative.runner import IterativeRunner
from experiments.iterative.transport import SanitizedTransportTracker, TrackedModelClient
from experiments.pilot.config import load_config
from experiments.pilot.model_client import DeepSeekCompatibleClient, MockModelClient
from ffjudge.runner import DockerJudge


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal failure-lineage experiment runner")
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=("dry-run", "mock", "live"))
    parser.add_argument("--run-id", default="minimal-failure-lineage-dry-run")
    parser.add_argument("--output-root")
    parser.add_argument("--mock-responses")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config = load_iterative_config(args.config)
    if args.mode:
        config = replace(config, mode=args.mode)
    if args.output_root:
        config = replace(config, output_root=str(Path(args.output_root).resolve()))
    project_root = Path(__file__).parents[1]
    if config.mode == "live":
        output = Path(config.output_root).resolve()
        if not args.output_root or output == project_root or output.is_relative_to(project_root):
            raise SystemExit("live lineage runs require --output-root outside the repository")
    if config.mode == "dry-run":
        result = IterativeRunner(config, project_root=project_root).dry_run(args.run_id)
    else:
        base = load_config(project_root / config.base_pilot_config)
        if args.mock_responses:
            base = replace(base, model=replace(
                base.model, mock_responses_path=str(Path(args.mock_responses).resolve())))
        image_id = "offline-fixture"
        if config.mode == "live":
            inspected = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}",
                 base.execution.judge_image], capture_output=True, text=True,
                check=False)
            if inspected.returncode or not inspected.stdout.strip():
                raise SystemExit("cannot freeze the configured Judge image ID")
            image_id = inspected.stdout.strip()
        if args.preflight_only:
            result = IterativeRunner(
                config, project_root=project_root, image_id=image_id).preflight(
                    args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if config.mode == "mock":
            model = MockModelClient(base.model)
            judge = DeterministicFakeJudge()
            flat_pipeline = (
                DeterministicStructuredFlatPipeline()
                if FLAT_V2_CONDITION in config.conditions
                else DeterministicFlatPipeline())
        else:
            tracker = SanitizedTransportTracker(
                Path(config.output_root) / args.run_id / "api_transport_attempts.jsonl")
            model = TrackedModelClient(
                DeepSeekCompatibleClient(base.model, opener=tracker), tracker)
            judge = DockerJudge(base.execution.judge_image)
            flat_pipeline = None
        result = IterativeRunner(
            config, project_root=project_root, model=model, judge=judge,
            flat_pipeline=flat_pipeline, image_id=image_id).run(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
