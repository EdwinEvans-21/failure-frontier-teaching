"""Frozen current-worktree snapshot for the 100-problem experiment bank."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


BASELINE_ID = "failure-frontier-baseline-v4-100-lc-snapshot"
SCHEMA_VERSION = "4.0"
DEFAULT_MANIFEST = Path("experiments/baseline_v4_100_lc_snapshot/baseline_manifest.json")
EXCLUDED_PROBLEM = "lc-0761-special-binary-string"
PROBLEM_FILES = {"problem.json", "benchmark_metadata.json", "public_tests.json", "hidden_tests.json", "stress_tests.json", "accepted.py", "complexity_canary.py", "mutants.json"}


def hash_file(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return sha256(payload).hexdigest(), "canonical_json_utf8_v1"
    try:
        payload = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        return sha256(payload).hexdigest(), "utf8_normalized_lf_v1"
    except UnicodeDecodeError:
        return sha256(path.read_bytes()).hexdigest(), "raw_bytes_v1"


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _dirty_paths(root: Path) -> list[str]:
    text = _git(root, "status", "--porcelain", "--untracked-files=all") or ""
    return sorted(line[3:].replace("\\", "/") for line in text.splitlines() if len(line) >= 4)


def problem_dirs(root: Path) -> list[Path]:
    return sorted(
        path for path in (root / "examples").glob("lc-*")
        if path.is_dir() and path.name != EXCLUDED_PROBLEM
    )


def discover_frozen_paths(root: Path) -> list[str]:
    paths: set[str] = {"Dockerfile", "pyproject.toml"}
    for directory in problem_dirs(root):
        for path in directory.iterdir():
            if path.is_file() and (path.name in PROBLEM_FILES or path.name.startswith("wrong_")):
                paths.add(path.relative_to(root).as_posix())
    for directory in (root / "src" / "ffjudge", root / "experiments" / "pilot", root / "experiments" / "iterative"):
        if directory.exists():
            paths.update(path.relative_to(root).as_posix() for path in directory.rglob("*.py"))
    for path in (root / "experiments" / "configs").glob("*.yaml"):
        paths.add(path.relative_to(root).as_posix())
    paths.update(path.relative_to(root).as_posix() for path in (root / "tools").glob("*baseline*.py"))
    paths.update({"tools/run_lc100_docker_validation.py", "tools/generate_v4_100_experiment_configs.py", "experiments/run_fresh_iterative.py"})
    missing = sorted(path for path in paths if not (root / path).is_file())
    if missing:
        raise FileNotFoundError(missing[0])
    if any(Path(path).name.lower() == "readme.md" for path in paths):
        raise ValueError("README must not enter frozen scope")
    return sorted(paths)


def problem_records(root: Path) -> list[dict[str, Any]]:
    rows = []
    for directory in problem_dirs(root):
        spec = json.loads((directory / "problem.json").read_text(encoding="utf-8-sig"))
        rows.append({
            "fixture": directory.name, "problem_id": spec["problem_id"], "role": spec["role"],
            "entrypoint": spec["entrypoint"], "comparison": spec["comparison"],
            "time_limit_seconds": spec["limits"]["time_seconds"], "memory_limit_mb": spec["limits"]["memory_mb"],
            "public_test_count": len(json.loads((directory / "public_tests.json").read_text(encoding="utf-8-sig"))),
            "hidden_test_count": len(json.loads((directory / "hidden_tests.json").read_text(encoding="utf-8-sig"))),
            "stress_test_count": len(json.loads((directory / "stress_tests.json").read_text(encoding="utf-8-sig"))),
        })
    return rows


def build_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve(); paths = discover_frozen_paths(root); dirty = _dirty_paths(root)
    frozen = []
    for name in paths:
        digest, mode = hash_file(root / name)
        frozen.append({"path": name, "sha256": digest, "hash_mode": mode})
    return {
        "baseline_id": BASELINE_ID, "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git(root, "rev-parse", "HEAD"),
        "working_tree_dirty_at_generation": bool(dirty),
        "dirty_path_count_at_generation": len(dirty),
        "source_commit_contains_frozen_state": False,
        "hash_policy": "canonical_json_utf8_v1 for JSON; utf8_normalized_lf_v1 for text; raw_bytes_v1 fallback",
        "scope": "100 lc fixtures excluding lc-0761; judge, pilot/iterative runner, relevant configs and baseline tools; README excluded",
        "problem_count": len(problem_dirs(root)), "problems": problem_records(root),
        "frozen_files": frozen,
        "scope_summary": {"frozen_file_count": len(frozen), "readme_frozen_count": 0},
        "validation_status_at_freeze": "snapshot_only; quality-gate findings are intentionally not represented as acceptance",
    }
