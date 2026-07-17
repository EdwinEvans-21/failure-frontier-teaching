from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

from experiments.pilot.config import load_config
from experiments.pilot.model_client import DeepSeekCompatibleClient, MockModelClient
from experiments.pilot.orchestrator import PilotRunner


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the five-problem Failure-Frontier Teaching pilot")
    result.add_argument("--config", required=True)
    result.add_argument("--run-id")
    result.add_argument("--mode", choices=["live", "mock", "dry-run"])
    result.add_argument("--mock-responses")
    result.add_argument("--output-root", help="override the artifact directory")
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
