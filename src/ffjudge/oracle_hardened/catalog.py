from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from ..oracles import expanded_dp as dp
from ..oracles import expanded_graph as graph
from ..oracles import expanded_misc as misc


@dataclass(frozen=True)
class HardenedProblem:
    number: int
    reference: Callable[..., Any]
    oracle: Callable[..., Any]
    seed: int
    exhaustive_bound: str
    adversarial_families: tuple[str, ...]
    stress_version: str = "stress_v3_1"


PROBLEMS: dict[int, HardenedProblem] = {
    1611: HardenedProblem(1611, misc.minimum_one_bit_reference, misc.minimum_one_bit_bruteforce, 1611003, "all n in [0,255]", ("zero", "powers-of-two", "gray-boundaries")),
    1786: HardenedProblem(1786, graph.count_restricted_paths_reference, graph.count_restricted_paths_bruteforce, 1786003, "connected graphs n<=7 sampled", ("equal-distance", "parallel-route", "strict-decrease")),
    1851: HardenedProblem(1851, misc.min_interval_reference, misc.min_interval_bruteforce, 1851003, "interval/query coordinates <=7 sampled", ("duplicates", "inclusive-boundary", "nested-intervals")),
    1896: HardenedProblem(1896, misc.expression_flip_reference, misc.expression_flip_bruteforce, 1896003, "valid expressions <=4 leaves sampled", ("deep-parentheses", "left-association", "operator-cheaper", "result-zero-one")),
    2071: HardenedProblem(2071, misc.max_task_assign_reference, misc.max_task_assign_bruteforce, 2071003, "arrays length<=6 sampled", ("pill-boundary", "zero-strength", "duplicates", "weakest-feasible-worker")),
    2203: HardenedProblem(2203, graph.minimum_weight_reference, graph.minimum_weight_bruteforce, 2203003, "directed graphs n<=7 sampled", ("unreachable", "shared-suffix", "meeting-endpoints")),
    2478: HardenedProblem(2478, dp.beautiful_partitions_reference, dp.beautiful_partitions_bruteforce, 2478003, "digit strings length<=9 sampled", ("first-last-prime", "exact-minLength", "prefix-indexing")),
    2809: HardenedProblem(2809, dp.minimum_time_reference, dp.minimum_time_bruteforce, 2809003, "arrays length<=7 sampled", ("knapsack-direction", "exactly-vs-at-most", "coefficient-order", "time-zero-n")),
    2940: HardenedProblem(2940, misc.leftmost_building_reference, misc.leftmost_building_bruteforce, 2940003, "heights length<=9 sampled", ("immediate-reach", "same-index", "equal-height", "strict-first-right")),
    2945: HardenedProblem(2945, dp.maximum_nondecreasing_length_reference, dp.maximum_nondecreasing_length_bruteforce, 2945003, "positive arrays length<=9 sampled", ("multiple-predecessors", "equal-prefix-boundary", "update-order", "last-segment")),
    3022: HardenedProblem(3022, misc.min_or_reference, misc.min_or_bruteforce, 3022003, "arrays length<=8 sampled", ("k-zero", "k-n-minus-one", "bit-boundaries")),
    3045: HardenedProblem(3045, misc.prefix_suffix_reference, misc.prefix_suffix_bruteforce, 3045003, "word lists length<=7 sampled", ("duplicates", "many-borders", "prefix-not-suffix")),
    3077: HardenedProblem(3077, dp.maximum_strength_reference, dp.maximum_strength_bruteforce, 3077003, "arrays length<=8 and odd k sampled", ("all-negative", "exact-k", "sign-transition")),
    3102: HardenedProblem(3102, misc.minimum_manhattan_reference, misc.minimum_manhattan_bruteforce, 3102003, "point sets length<=8 sampled", ("duplicates", "remove-extreme", "tied-transforms")),
    3117: HardenedProblem(3117, dp.minimum_value_sum_reference, dp.minimum_value_sum_bruteforce, 3117003, "arrays length<=8, targets<=4 sampled", ("must-end-at-n", "repeated-target", "multiple-matches", "and-compression", "singletons", "no-solution", "first-match-only")),
    3123: HardenedProblem(3123, graph.find_answer_reference, graph.find_answer_bruteforce, 3123003, "simple connected graphs n<=7 sampled", ("multiple-shortest-paths", "equal-distance", "irrelevant-edge")),
}


def examples_dir(repo_root: Path, number: int) -> Path:
    matches = sorted((repo_root / "examples").glob(f"lc-{number:04d}-*"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one example directory for lc-{number}, found {len(matches)}")
    return matches[0]
