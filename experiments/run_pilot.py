from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

from experiments.pilot.config import load_config
from experiments.pilot.model_client import DeepSeekCompatibleClient, MockModelClient
from experiments.pilot.orchestrator import PilotRunner
from experiments.pilot.api_check import run_api_compatibility_check


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the five-problem Failure-Frontier Teaching pilot")
    result.add_argument("--config", required=True)
    result.add_argument("--run-id")
    result.add_argument("--mode", choices=["live", "mock", "dry-run", "api-check", "smoke-test"])
    result.add_argument("--mock-responses")
    result.add_argument("--output-root", help="override the artifact directory")
    result.add_argument("--problem-id", help="single configured problem for smoke-test")
    return result


def main() -> None:
    args = parser().parse_args()
    config = load_config(args.config)
    if args.mode:
        config = replace(config, mode=args.mode)
    if args.mock_responses:
        config = replace(config, model=replace(
            config.model, mock_responses_path=str(Path(args.mock_responses).resolve())))
    if args.output_root:
        config = replace(config, execution=replace(
            config.execution, output_root=str(Path(args.output_root).resolve())))
    if config.mode == "api-check":
        if not args.output_root:
            raise SystemExit("--output-root is required for api-check")
        verifier = PilotRunner(config, None, judge=object())
        verifier.verify_baseline()
        client = DeepSeekCompatibleClient(config.model)
        result = run_api_compatibility_check(
            config, client, args.output_root, project_root=Path.cwd())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    if config.mode == "smoke-test":
        if not args.output_root or not args.problem_id:
            raise SystemExit("--output-root and --problem-id are required for smoke-test")
        model = DeepSeekCompatibleClient(config.model)
        result = PilotRunner(config, model).run_smoke(
            args.problem_id, args.output_root, args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    if config.mode == "dry-run":
        model = None
    elif config.mode == "mock":
        model = MockModelClient(config.model)
    else:
        model = DeepSeekCompatibleClient(config.model)
    result = PilotRunner(config, model).run(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
