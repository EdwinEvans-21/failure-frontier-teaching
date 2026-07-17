"""Shared definitions for the problem-and-judge baseline v3."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import subprocess

from baseline_v2 import (
    category,
    discover_frozen_paths,
    generator_records,
    hash_file,
    problem_records,
)
from baseline_v2 import build_manifest as _build_v2_manifest


BASELINE_ID = "failure-frontier-baseline-v3"
SCHEMA_VERSION = "3.0"
DEFAULT_MANIFEST = Path("experiments/baseline_v3/baseline_manifest.json")


def _dirty_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        return []
    paths = []
    for line in completed.stdout.splitlines():
        if len(line) >= 4:
            paths.append(line[3:].replace("\\", "/"))
    return sorted(paths)


def build_manifest(
    root: Path,
    *,
    source_commit: str | None = None,
    created_at: str | None = None,
    generator_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest = _build_v2_manifest(
        root,
        source_commit=source_commit,
        created_at=created_at,
        generator_verification=generator_verification,
    )
    frozen_paths = {item["path"] for item in manifest["frozen_files"]}
    dirty_paths = _dirty_paths(root)
    dirty_frozen_paths = sorted(frozen_paths.intersection(dirty_paths))
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["baseline_id"] = BASELINE_ID
    manifest["scope_rules"]["policy"] = (
        "explicit_problem_and_judge_allowlist_v3"
    )
    manifest["scope_summary"] = {
        "frozen_file_count": len(manifest["frozen_files"]),
        "readme_frozen_count": sum(
            Path(item["path"]).name.lower() == "readme.md"
            for item in manifest["frozen_files"]
        ),
    }
    manifest["judge_timing_policy"] = {
        "runtime_source": "container_harness_monotonic_clock",
        "start_boundary": (
            "immediately_before_submission_module_loading"
        ),
        "end_boundary": "immediately_after_entrypoint_returns_or_raises",
        "docker_startup_included": False,
        "docker_host_watchdog_verdict": "INTERNAL_ERROR",
        "submission_execution_timeout_verdict": "TIME_LIMIT_EXCEEDED",
    }
    manifest["environment"]["working_tree_dirty_at_generation"] = bool(
        dirty_paths
    )
    manifest["environment"]["dirty_frozen_paths_at_generation"] = (
        dirty_frozen_paths
    )
    manifest["environment"]["source_commit_contains_frozen_state"] = not bool(
        dirty_frozen_paths
    )
    return manifest
