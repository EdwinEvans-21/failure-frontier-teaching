"""Shared definitions for the semantic-only benchmark baseline v2."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import platform
import re
import subprocess


BASELINE_ID = "failure-frontier-baseline-v2"
SCHEMA_VERSION = "2.0"
DEFAULT_MANIFEST = Path("experiments/baseline_v2/baseline_manifest.json")

PROBLEMS = (
    "palindrome_number",
    "exact_monotone_paths",
    "minimum_operations_binary_transform",
    "sorted_gcd_pair_queries",
    "maximum_subarray_sum_after_k_swaps",
)

PRESSURE_COUNTS = {
    "palindrome_number": 0,
    "exact_monotone_paths": 0,
    "minimum_operations_binary_transform": 3,
    "sorted_gcd_pair_queries": 3,
    "maximum_subarray_sum_after_k_swaps": 7,
}

GENERATORS = {
    "palindrome_number": None,
    "exact_monotone_paths": None,
    "minimum_operations_binary_transform":
        "tools/generate_minimum_operations_binary_transform_tests.py",
    "sorted_gcd_pair_queries":
        "tools/generate_sorted_gcd_pair_queries_tests.py",
    "maximum_subarray_sum_after_k_swaps":
        "tools/generate_maximum_subarray_sum_after_k_swaps_tests.py",
}

CORE_SEMANTIC_FILES = (
    "Dockerfile",
    "pyproject.toml",
    "src/ffjudge/__init__.py",
    "src/ffjudge/cli.py",
    "src/ffjudge/harness.py",
    "src/ffjudge/models.py",
    "src/ffjudge/runner.py",
    "src/ffjudge/checkers/__init__.py",
    "src/ffjudge/checkers/exact_monotone_paths.py",
    "src/ffjudge/oracles/__init__.py",
    "src/ffjudge/oracles/exact_monotone_paths.py",
    "src/ffjudge/oracles/minimum_operations_binary_transform.py",
    "src/ffjudge/oracles/sorted_gcd_pair_queries.py",
    "src/ffjudge/oracles/maximum_subarray_sum_after_k_swaps.py",
    "tools/verify_formal_test_generators.py",
)


def _run(command: list[str], root: Path) -> str | None:
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True,
            timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def canonical_json_bytes(path: Path) -> bytes:
    value = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def hash_file(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".json":
        payload = canonical_json_bytes(path)
        mode = "canonical_json_utf8_v1"
    else:
        try:
            text = path.read_text(encoding="utf-8")
            payload = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            mode = "utf8_normalized_lf_v1"
        except UnicodeDecodeError:
            payload = path.read_bytes()
            mode = "raw_bytes_v1"
    return sha256(payload).hexdigest(), mode


def discover_frozen_paths(root: Path) -> list[str]:
    paths = set(CORE_SEMANTIC_FILES)
    for slug in PROBLEMS:
        for name in ("problem.json", "public_tests.json", "hidden_tests.json"):
            paths.add(f"examples/{slug}/{name}")
        generator = GENERATORS[slug]
        if generator:
            paths.add(generator)
    paths = {path for path in paths if Path(path).name.lower() != "readme.md"}
    missing = sorted(path for path in paths if not (root / path).is_file())
    if missing:
        raise FileNotFoundError("missing v2 frozen-scope file: " + missing[0])
    return sorted(paths)


def category(path: str) -> str:
    if path.endswith("problem.json"):
        return "canonical_problem_specification"
    if path.endswith("public_tests.json"):
        return "public_tests"
    if path.endswith("hidden_tests.json"):
        return "trusted_hidden_tests"
    if "/oracles/" in path:
        return "trusted_oracle"
    if "/checkers/" in path:
        return "trusted_checker"
    if path.startswith("tools/generate_"):
        return "formal_test_generator"
    if path == "Dockerfile":
        return "pinned_judge_environment"
    return "judge_semantics"


def problem_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for slug in PROBLEMS:
        fixture = root / "examples" / slug
        spec = json.loads((fixture / "problem.json").read_text(encoding="utf-8"))
        public = json.loads((fixture / "public_tests.json").read_text(encoding="utf-8"))
        hidden = json.loads((fixture / "hidden_tests.json").read_text(encoding="utf-8"))
        records.append({
            "fixture": slug,
            "problem_id": spec["problem_id"],
            "role": spec["role"],
            "entrypoint": spec["entrypoint"],
            "comparison": spec["comparison"],
            "checker": spec.get("checker", ""),
            "time_limit_seconds": spec["limits"]["time_seconds"],
            "memory_limit_mb": spec["limits"]["memory_mb"],
            "public_test_count": len(public),
            "hidden_test_count": len(hidden),
            "pressure_test_count": PRESSURE_COUNTS[slug],
        })
    return records


def generator_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for slug in PROBLEMS:
        path = GENERATORS[slug]
        if path is None:
            records.append({
                "fixture": slug, "path": None, "deterministic": None,
                "random_seed": None, "check": "no_formal_generator_present",
            })
            continue
        source = (root / path).read_text(encoding="utf-8")
        seeds = [int(value) for value in re.findall(r"\bRandom\((\d+)\)", source)]
        uses_random = bool(re.search(
            r"\b(?:random|randint|randrange|choice|shuffle)\b", source
        ))
        records.append({
            "fixture": slug,
            "path": path,
            "deterministic": not uses_random or bool(seeds),
            "random_seed": seeds[0] if len(set(seeds)) == 1 else None,
            "check": "static_source_scan_plus_temporary_regeneration",
        })
    return records


def environment_record(root: Path, source_commit: str | None) -> dict[str, Any]:
    versions = _run(
        ["docker", "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"],
        root,
    )
    client = server = None
    if versions and "|" in versions:
        client, server = versions.split("|", 1)
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"^FROM\s+(\S+)", dockerfile, re.MULTILINE)
    base_image = match.group(1) if match else None
    return {
        "python_version": platform.python_version(),
        "docker_client_version": client,
        "docker_server_version": server,
        "ffjudge_image_id": _run(
            ["docker", "image", "inspect", "ffjudge-python:latest", "--format", "{{.Id}}"],
            root,
        ),
        "base_image": base_image,
        "base_image_repo_digest": base_image.split("@", 1)[1] if base_image and "@" in base_image else None,
        "source_commit": source_commit or _run(["git", "rev-parse", "HEAD"], root),
        "authority": (
            "source_commit identifies the commit containing benchmark code and data; "
            "the authoritative baseline tag points to the later manifest-only commit."
        ),
    }


def build_manifest(
    root: Path,
    *,
    source_commit: str | None = None,
    created_at: str | None = None,
    generator_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    files = []
    for relative in discover_frozen_paths(root):
        digest, mode = hash_file(root / relative)
        files.append({
            "path": relative,
            "category": category(relative),
            "sha256": digest,
            "hash_mode": mode,
        })
    generators = generator_records(root)
    if any(item["deterministic"] is False for item in generators):
        raise RuntimeError("a formal test generator uses unseeded randomness")
    by_fixture = {
        item["fixture"]: item
        for item in (generator_verification or {}).get("generators", [])
    }
    for item in generators:
        item["temporary_regeneration"] = by_fixture.get(
            item["fixture"], {"result": "not_checked"}
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_id": BASELINE_ID,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "environment": environment_record(root, source_commit),
        "scope_rules": {
            "policy": "explicit_semantic_allowlist",
            "included": [
                "canonical problem.json files",
                "public and hidden formal tests",
                "trusted oracles and custom checker",
                "judge execution and verdict semantics",
                "formal test generators",
                "pinned Dockerfile and Python package metadata",
            ],
            "excluded": [
                "any path whose basename case-insensitively equals README.md",
                "research prompts and experiment runner",
                "protocol and explanatory documents",
                "run artifacts, caches, logs, and local environment files",
                "accepted and intentionally wrong submissions",
                ".gitignore and other development-only configuration",
            ],
            "readme_exclusion_case_insensitive": True,
        },
        "hash_strategy": {
            "json": "Canonical UTF-8 JSON with sorted object keys; array order and numeric types are preserved.",
            "text": "UTF-8 text normalized from CRLF/CR to LF before SHA-256.",
            "binary": "SHA-256 of raw bytes.",
        },
        "problems": problem_records(root),
        "formal_test_generators": generators,
        "frozen_files": files,
    }

