from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
import hashlib


PROBLEM_IDS = (
    "lc-1786-number-of-restricted-paths-from-first-to-last-node",
    "lc-1851-minimum-interval-to-include-each-query",
    "lc-2809-minimum-time-to-make-array-sum-at-most-x",
    "lc-2940-find-building-where-alice-and-bob-can-meet",
    "lc-2945-find-maximum-non-decreasing-array-length",
    "lc-3022-minimize-or-of-remaining-elements-using-operations",
    "lc-3077-maximum-strength-of-k-disjoint-subarrays",
)

CONDITIONS = ("baseline", "naive_ff", "critical_ff", "general_guidance")


def build_schedule(run_id: str, replicates: int = 10) -> list[dict[str, Any]]:
    """Build a deterministic Latin-rotation schedule of 70 four-condition blocks."""
    if replicates != 10:
        raise ValueError("fixed-material v1 requires exactly 10 replicates")
    offset = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % 4
    schedule: list[dict[str, Any]] = []
    ordinal = 0
    for replicate in range(replicates):
        problem_rotation = replicate % len(PROBLEM_IDS)
        problems = PROBLEM_IDS[problem_rotation:] + PROBLEM_IDS[:problem_rotation]
        for problem_id in problems:
            problem_index = PROBLEM_IDS.index(problem_id)
            rotation = (replicate + problem_index + offset) % 4
            order = CONDITIONS[rotation:] + CONDITIONS[:rotation]
            for position, condition in enumerate(order, 1):
                schedule.append({
                    "ordinal": ordinal,
                    "block_index": ordinal // 4,
                    "problem_id": problem_id,
                    "replicate_index": replicate,
                    "condition": condition,
                    "condition_position": position,
                    "cell_id": f"{problem_id}__{condition}__r{replicate:02d}",
                })
                ordinal += 1
    validate_schedule(schedule)
    return schedule


def validate_schedule(schedule: list[dict[str, Any]]) -> None:
    if len(schedule) != 280:
        raise ValueError("schedule must contain exactly 280 cells")
    keys = {
        (row["problem_id"], row["condition"], row["replicate_index"])
        for row in schedule
    }
    if len(keys) != 280:
        raise ValueError("schedule contains duplicate sample cells")
    global_positions: dict[str, Counter[int]] = defaultdict(Counter)
    per_problem_positions: dict[tuple[str, str], Counter[int]] = defaultdict(Counter)
    for row in schedule:
        global_positions[row["condition"]][row["condition_position"]] += 1
        per_problem_positions[(row["problem_id"], row["condition"])][
            row["condition_position"]
        ] += 1
    for counts in global_positions.values():
        if max(counts.values()) - min(counts.values()) > 1:
            raise ValueError("global condition positions are unbalanced")
    for counts in per_problem_positions.values():
        if max(counts.values()) - min(counts.values()) > 1:
            raise ValueError("per-problem condition positions are unbalanced")
