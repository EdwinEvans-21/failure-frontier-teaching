from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from .runner import DockerJudge, DockerUnavailableError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ffjudge")
    root.add_argument("--image", default="ffjudge-python:latest")
    commands = root.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build the judge Docker image")
    build.add_argument("--project-root",
                       default=str(Path(__file__).parents[2]))

    judge = commands.add_parser("judge", help="judge one Python submission")
    judge.add_argument("--submission", required=True)
    judge.add_argument("--problem", required=True)
    judge.add_argument("--tests", required=True)
    judge.add_argument("--phase",
                       choices=["public", "hidden"],
                       default="hidden")
    judge.add_argument(
        "--view",
        choices=["internal", "model"],
        default="internal",
        help="emit the full research record or model-safe feedback",
    )
    return root


def main() -> None:
    args = parser().parse_args()
    judge = DockerJudge(args.image)
    try:
        if args.command == "build":
            judge.build_image(args.project_root)
            return
        result = judge.judge(
            args.submission,
            args.problem,
            args.tests,
            phase=args.phase,
        )
        payload = result.to_dict(
        ) if args.view == "internal" else result.model_feedback()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (DockerUnavailableError, FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
