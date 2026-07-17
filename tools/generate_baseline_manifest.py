"""Generate the versioned Failure-Frontier baseline manifest."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import argparse
import json
import platform
import re
import subprocess


BASELINE_ID = "failure-frontier-baseline-v1"
SCHEMA_VERSION = "1.0"
DEFAULT_OUTPUT = Path("experiments/baseline_v1/baseline_manifest.json")

PROBLEMS = (
    ("palindrome_number", 0),
    ("exact_monotone_paths", 0),
    ("minimum_operations_binary_transform", 3),
    ("sorted_gcd_pair_queries", 3),
    ("maximum_subarray_sum_after_k_swaps", 7),
)

GENERATOR_BY_PROBLEM = {
    "palindrome_number": None,
    "exact_monotone_paths": None,
    "minimum_operations_binary_transform": (
        "tools/generate_minimum_operations_binary_transform_tests.py"
    ),
    "sorted_gcd_pair_queries": (
        "tools/generate_sorted_gcd_pair_queries_tests.py"
    ),
    "maximum_subarray_sum_after_k_swaps": (
        "tools/generate_maximum_subarray_sum_after_k_swaps_tests.py"
    ),
}

BASELINE_DOCUMENTS = (
    "experiments/baseline_v1/protocol.md",
    "experiments/baseline_v1/experiment_config.example.json",
    "experiments/baseline_v1/run_record.schema.json",
    "experiments/baseline_v1/initial_prompt.template.md",
    "experiments/baseline_v1/feedback_templates.json",
)

DIRTY_IGNORED_PATHS = {
    "experiments/baseline_v1/baseline_manifest.json",
    "docker-full-test.log",
}


def _run(command: list[str], root: Path) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def canonical_json_bytes(path: Path) -> bytes:
    value = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def normalized_text_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def hash_file(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".json":
        payload = canonical_json_bytes(path)
        mode = "canonical_json_utf8_v1"
    else:
        try:
            payload = normalized_text_bytes(path)
            mode = "utf8_normalized_lf_v1"
        except UnicodeDecodeError:
            payload = path.read_bytes()
            mode = "raw_bytes_v1"
    return sha256(payload).hexdigest(), mode


def discover_frozen_paths(root: Path) -> list[str]:
    paths: set[str] = set()

    def add(path: Path) -> None:
        if (path.is_file() and "__pycache__" not in path.parts
                and path.suffix != ".pyc"):
            paths.add(path.relative_to(root).as_posix())

    for slug, _ in PROBLEMS:
        problem_root = root / "examples" / slug
        for path in problem_root.rglob("*"):
            add(path)

    for relative in (
        "README.md",
        "Dockerfile",
        ".dockerignore",
        ".gitignore",
        "pyproject.toml",
        "src/ffjudge/__init__.py",
        "src/ffjudge/cli.py",
        "src/ffjudge/harness.py",
        "src/ffjudge/models.py",
        "src/ffjudge/runner.py",
        "tools/generate_baseline_manifest.py",
        "tools/verify_baseline_manifest.py",
        "tools/verify_formal_test_generators.py",
        *BASELINE_DOCUMENTS,
    ):
        add(root / relative)

    for directory, pattern in (
        ("src/ffjudge/checkers", "*.py"),
        ("src/ffjudge/oracles", "*.py"),
        ("tools", "generate_*_tests.py"),
        ("tests", "test_*.py"),
    ):
        for path in (root / directory).glob(pattern):
            add(path)

    return sorted(paths)


def file_category(path: str) -> str:
    if path.startswith("examples/"):
        return "problem_fixture"
    if "/oracles/" in path or "/checkers/" in path:
        return "trusted_oracle_or_checker"
    if path.startswith("tests/"):
        return "automated_test"
    if path.startswith("tools/generate_") and path.endswith("_tests.py"):
        return "formal_test_generator"
    if path.startswith("tools/"):
        return "baseline_tool"
    if path.startswith("experiments/"):
        return "experiment_protocol"
    return "judge_or_project_infrastructure"


def read_problem_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for slug, pressure_count in PROBLEMS:
        directory = root / "examples" / slug
        spec = json.loads((directory / "problem.json").read_text(encoding="utf-8"))
        public = json.loads((directory / "public_tests.json").read_text(encoding="utf-8"))
        hidden = json.loads((directory / "hidden_tests.json").read_text(encoding="utf-8"))
        records.append({
            "fixture": slug,
            "problem_id": spec["problem_id"],
            "role": spec["role"],
            "entrypoint": spec["entrypoint"],
            "comparison": spec["comparison"],
            "time_limit_seconds": spec["limits"]["time_seconds"],
            "memory_limit_mb": spec["limits"]["memory_mb"],
            "public_test_count": len(public),
            "hidden_test_count": len(hidden),
            "pressure_test_count": pressure_count,
        })
    return records


def inspect_generator_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for slug, _ in PROBLEMS:
        relative = GENERATOR_BY_PROBLEM[slug]
        if relative is None:
            records.append({
                "fixture": slug,
                "path": None,
                "deterministic": None,
                "random_seed": None,
                "check": "no_formal_generator_present",
            })
            continue
        source = (root / relative).read_text(encoding="utf-8")
        seeds = [int(value) for value in re.findall(r"\bRandom\((\d+)\)", source)]
        uses_random = bool(re.search(r"\b(?:random|randint|randrange|choice|shuffle)\b", source))
        deterministic = not uses_random or bool(seeds)
        records.append({
            "fixture": slug,
            "path": relative,
            "deterministic": deterministic,
            "random_seed": seeds[0] if len(set(seeds)) == 1 else None,
            "check": "static_source_scan",
        })
    return records


def source_worktree_changes(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0 or not completed.stdout:
        return []
    changed = []
    for line in completed.stdout.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"').replace("\\", "/")
        if path not in DIRTY_IGNORED_PATHS:
            changed.append(path)
    return sorted(changed)


def environment_record(root: Path) -> dict[str, Any]:
    docker_version = _run(
        ["docker", "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"],
        root,
    )
    client_version = server_version = None
    if docker_version and "|" in docker_version:
        client_version, server_version = docker_version.split("|", 1)

    repo_digests_raw = _run(
        ["docker", "image", "inspect", "python:3.12-slim", "--format", "{{json .RepoDigests}}"],
        root,
    )
    repo_digests = json.loads(repo_digests_raw) if repo_digests_raw else []
    base_digest = next(
        (digest for digest in repo_digests if digest.startswith("python@sha256:")),
        None,
    )
    return {
        "python_version": platform.python_version(),
        "docker_client_version": client_version,
        "docker_server_version": server_version,
        "ffjudge_image_id": _run(
            ["docker", "image", "inspect", "ffjudge-python:latest", "--format", "{{.Id}}"],
            root,
        ),
        "base_image": "python:3.12-slim",
        "base_image_repo_digest": base_digest,
        "source_commit": _run(["git", "rev-parse", "HEAD"], root),
        "source_worktree_dirty": bool(source_worktree_changes(root)),
        "dirty_ignored_paths": sorted(DIRTY_IGNORED_PATHS),
        "authority": (
            "The authoritative baseline tag points to a later manifest-only commit; "
            "source_commit identifies the commit containing frozen judge code and data."
        ),
    }


def build_manifest(
    root: Path,
    *,
    created_at: str | None = None,
    generator_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    frozen_files = []
    for relative in discover_frozen_paths(root):
        digest, mode = hash_file(root / relative)
        frozen_files.append({
            "path": relative,
            "category": file_category(relative),
            "sha256": digest,
            "hash_mode": mode,
        })
    generators = inspect_generator_records(root)
    if generator_verification is not None:
        by_fixture = {
            record["fixture"]: record
            for record in generator_verification["generators"]
        }
        for record in generators:
            record["temporary_regeneration"] = by_fixture.get(
                record["fixture"],
                {"result": "not_checked"},
            )
    if any(record["deterministic"] is False for record in generators):
        raise RuntimeError("a formal test generator uses unseeded randomness")
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_id": BASELINE_ID,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "environment": environment_record(root),
        "hash_strategy": {
            "json": "Parse UTF-8 JSON, then SHA-256 compact UTF-8 JSON with sorted object keys; array order and numeric types are preserved.",
            "text": "Decode UTF-8, normalize CRLF and CR to LF, then SHA-256 the UTF-8 bytes.",
            "binary": "SHA-256 raw bytes.",
        },
        "pressure_test_definition": (
            "Explicit maximum-scale/performance cases maintained by each fixture's tests or generator; boundary-only cases are not counted as pressure cases."
        ),
        "problems": read_problem_records(root),
        "formal_test_generators": generators,
        "frozen_files": frozen_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-generators", action="store_true")
    parser.add_argument("--reuse-generator-verification-from", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    verification = None
    if args.verify_generators and args.reuse_generator_verification_from:
        parser.error("generator verification options are mutually exclusive")
    if args.verify_generators:
        from verify_formal_test_generators import verify_generators
        verification = verify_generators(root)
        failures = [
            record for record in verification["generators"]
            if record["result"] not in {
                "byte_identical",
                "not_applicable_no_generator",
            }
        ]
        if failures:
            raise RuntimeError("formal test regeneration did not match frozen files")
    elif args.reuse_generator_verification_from:
        source = args.reuse_generator_verification_from
        if not source.is_absolute():
            source = root / source
        previous = json.loads(source.read_text(encoding="utf-8"))
        verification = {
            "generators": [
                record["temporary_regeneration"]
                for record in previous["formal_test_generators"]
            ]
        }
    manifest = build_manifest(root, generator_verification=verification)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output} with {len(manifest['frozen_files'])} frozen files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
