from __future__ import annotations

from pathlib import Path
import argparse
import json
import os

from experiments.fixed_material.runner import FixedMaterialRunner, now
from experiments.fixed_material.source import (
    build_fixed_material_snapshot,
    verify_fixed_material_snapshot,
)
from experiments.pilot.storage import write_json


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Fixed-Material Repeated Student Experiment v1"
    )
    result.add_argument("--config", default="experiments/configs/fixed_material_repeats_v1.json")
    result.add_argument("--mode", choices=("snapshot", "verify-source", "dry-run", "mock", "live"), required=True)
    result.add_argument("--source-run")
    result.add_argument("--snapshot-root", required=True)
    result.add_argument("--output-root")
    result.add_argument("--run-id")
    result.add_argument("--resume", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    project_root = Path.cwd().resolve()
    snapshot_root = Path(args.snapshot_root).resolve()
    if args.mode == "snapshot":
        if not args.source_run:
            raise SystemExit("--source-run is required for snapshot mode")
        result = build_fixed_material_snapshot(
            Path(args.source_run), snapshot_root, project_root
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.mode == "verify-source":
        result = verify_fixed_material_snapshot(snapshot_root, project_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    if not args.output_root:
        raise SystemExit("--output-root is required")
    run_id = args.run_id or "fixed-material-repeats-v1-" + now().replace(
        "-", ""
    ).replace(":", "").replace("+00:00", "Z").split(".")[0]
    runner = FixedMaterialRunner(
        Path(args.config), snapshot_root, Path(args.output_root),
        mode=args.mode, project_root=project_root,
    )
    if args.mode == "dry-run":
        result = runner.dry_run(run_id)
    elif args.resume:
        result = runner.run(run_id, resume=True)
    else:
        preflight = runner.preflight(run_id)
        assert runner.run_dir is not None
        write_json(runner.run_dir / "launch_record.json", {
            "run_id": run_id,
            "launched_at": now(),
            "pid": os.getpid(),
            "mode": args.mode,
            "resume": False,
            "command": "python -m experiments.run_fixed_material",
            "preflight_manifest_sha256": preflight["fixed_material_manifest_sha256"],
        })
        result = runner.run(run_id, resume=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
