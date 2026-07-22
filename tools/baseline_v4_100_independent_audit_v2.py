"""Independent-oracle-audited successor snapshot for the 100-problem bank."""
from __future__ import annotations

from pathlib import Path
from baseline_v4_100 import build_manifest as _base_build, discover_frozen_paths, hash_file, problem_records

BASELINE_ID = "failure-frontier-baseline-v4-100-lc-independent-audit-v2"
SCHEMA_VERSION = "4.1"
DEFAULT_MANIFEST = Path("experiments/baseline_v4_100_lc_independent_audit_v2/baseline_manifest.json")


def build_manifest(root: Path) -> dict:
    manifest = _base_build(root)
    manifest["baseline_id"] = BASELINE_ID
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["scope"] += "; audit-v2 adds deterministic independent small-oracle regressions"
    manifest["validation_status_at_freeze"] = "independent_oracle_regressions_verified_before_snapshot"
    return manifest
