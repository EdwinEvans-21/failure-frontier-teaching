"""Fixed-material repeated Student experiment."""

from .schedule import CONDITIONS, PROBLEM_IDS, build_schedule
from .source import build_fixed_material_snapshot, verify_fixed_material_snapshot

__all__ = [
    "CONDITIONS",
    "PROBLEM_IDS",
    "build_schedule",
    "build_fixed_material_snapshot",
    "verify_fixed_material_snapshot",
]
