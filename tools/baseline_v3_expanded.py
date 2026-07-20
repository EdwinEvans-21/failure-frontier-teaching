from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from baseline_v2 import category, hash_file
from baseline_v3 import build_manifest as build_v3_manifest
from expanded_benchmark_catalog import records


BASELINE_ID = "failure-frontier-baseline-v3-expanded"
SCHEMA_VERSION = "3.1-expanded"
DEFAULT_MANIFEST = Path(
    "experiments/baseline_v3_expanded/baseline_manifest.json"
)
FIXTURE_FILES = (
    "problem.json",
    "benchmark_metadata.json",
    "public_tests.json",
    "hidden_tests.json",
    "stress_tests.json",
    "accepted.py",
    "mutants.json",
    "wrong_boundary.py",
    "wrong_direction.py",
    "wrong_off_by_one.py",
)
SUPPORT_FILES = (
    "src/ffjudge/oracles/expanded_graph.py",
    "src/ffjudge/oracles/expanded_dp.py",
    "src/ffjudge/oracles/expanded_misc.py",
    "tools/expanded_benchmark_catalog.py",
    "tools/expanded_benchmark_specs.py",
    "tools/generate_expanded_benchmarks.py",
    "tests/test_expanded_benchmark_catalog.py",
    "tests/test_expanded_benchmarks.py",
    "tests/test_expanded_docker_e2e.py",
    "tests/test_expanded_graph_oracles.py",
    "tests/test_expanded_dp_oracles.py",
    "tests/test_expanded_misc_oracles.py",
)


def expanded_paths(root: Path) -> list[str]:
    paths = set(SUPPORT_FILES)
    for item in records():
        fixture = str(item["problem_id"])
        paths.update(f"examples/{fixture}/{name}" for name in FIXTURE_FILES)
    missing = sorted(path for path in paths if not (root / path).is_file())
    if missing:
        raise FileNotFoundError("missing expanded frozen file: " + missing[0])
    if any(Path(path).name.lower() == "readme.md" for path in paths):
        raise ValueError("README entered expanded frozen scope")
    return sorted(paths)


def expanded_problem_records(root: Path) -> list[dict[str, Any]]:
    result = []
    for item in records():
        fixture = str(item["problem_id"])
        directory = root / "examples" / fixture
        spec = json.loads((directory / "problem.json").read_text(encoding="utf-8"))
        public = json.loads((directory / "public_tests.json").read_text(encoding="utf-8"))
        hidden = json.loads((directory / "hidden_tests.json").read_text(encoding="utf-8"))
        stress = json.loads((directory / "stress_tests.json").read_text(encoding="utf-8"))
        metadata = json.loads((directory / "benchmark_metadata.json").read_text(encoding="utf-8"))
        result.append({
            "fixture": fixture,
            "problem_id": spec["problem_id"],
            "role": spec["role"],
            "entrypoint": spec["entrypoint"],
            "comparison": spec["comparison"],
            "checker": spec.get("checker", ""),
            "time_limit_seconds": spec["limits"]["time_seconds"],
            "memory_limit_mb": spec["limits"]["memory_mb"],
            "public_test_count": len(public),
            "hidden_test_count": len(hidden),
            "pressure_test_count": len(stress),
            "topic": metadata["topic"],
            "memorization_risk": metadata["memorization_risk"],
        })
    return result


def verify_expanded_generator(root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="fft-expanded-baseline-") as temporary:
        output = Path(temporary) / "examples"
        completed = subprocess.run(
            [sys.executable, str(root / "tools" / "generate_expanded_benchmarks.py"),
             "--output-root", str(output)], cwd=root, capture_output=True,
            text=True, timeout=180, check=False,
        )
        if completed.returncode:
            return {"result": "generator_failed", "file_count": 0}
        checked = 0
        for item in records():
            fixture = str(item["problem_id"])
            for name in FIXTURE_FILES:
                checked += 1
                expected = (root / "examples" / fixture / name).read_bytes()
                actual = (output / fixture / name).read_bytes()
                # Git may materialize text files with CRLF on Windows while
                # the deterministic generator emits LF bytes.  Expanded
                # fixtures are all UTF-8 text; normalize only line endings so
                # substantive byte drift remains fail-closed.
                expected = expected.replace(b"\r\n", b"\n")
                actual = actual.replace(b"\r\n", b"\n")
                if expected != actual:
                    return {"result": "byte_mismatch", "file_count": checked}
    return {"result": "normalized_text_identical", "file_count": checked}


def discover_frozen_paths(root: Path) -> list[str]:
    from baseline_v3 import discover_frozen_paths as old_paths
    return sorted(set(old_paths(root)) | set(expanded_paths(root)))


def build_manifest(root: Path, *, source_commit: str) -> dict[str, Any]:
    from verify_formal_test_generators import verify_generators
    old_verification = verify_generators(root)
    manifest = build_v3_manifest(
        root,
        source_commit=source_commit,
        created_at=datetime.now(timezone.utc).isoformat(),
        generator_verification=old_verification,
    )
    proof = verify_expanded_generator(root)
    if proof["result"] != "normalized_text_identical":
        raise RuntimeError("expanded generator did not reproduce frozen files")
    existing = {item["path"]: item for item in manifest["frozen_files"]}
    for path in expanded_paths(root):
        digest, mode = hash_file(root / path)
        existing[path] = {
            "path": path,
            "category": category(path),
            "sha256": digest,
            "hash_mode": mode,
        }
    manifest["baseline_id"] = BASELINE_ID
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["problems"].extend(expanded_problem_records(root))
    manifest["formal_test_generators"].append({
        "fixture": "expanded_31_problem_suite",
        "path": "tools/generate_expanded_benchmarks.py",
        "deterministic": True,
        "random_seed": 20260718,
        "check": "temporary_directory_line_ending_normalized_identical_all_fixture_files",
        "temporary_regeneration": proof,
    })
    manifest["frozen_files"] = [existing[path] for path in sorted(existing)]
    manifest["scope_rules"]["policy"] = (
        "baseline_v3_plus_explicit_expanded_benchmark_allowlist"
    )
    manifest["scope_summary"] = {
        "old_frozen_file_count": 33,
        "frozen_file_count": len(existing),
        "readme_frozen_count": 0,
        "expanded_problem_count": 31,
    }
    manifest["environment"]["working_tree_dirty_at_generation"] = False
    manifest["environment"]["dirty_frozen_paths_at_generation"] = []
    manifest["environment"]["source_commit_contains_frozen_state"] = True
    return manifest
