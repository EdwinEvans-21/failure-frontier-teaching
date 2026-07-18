from __future__ import annotations

from typing import Final


EXPANDED_BASELINE_ID: Final = "failure-frontier-baseline-v3-expanded"

GRAPH = "graph_connectivity"
DP = "dynamic_programming_optimization"
GREEDY = "greedy_offline_data_structures"
BITS = "bit_string_expression"


PROBLEMS: Final = (
    (3123, "find-edges-in-shortest-paths", "findAnswer", ("n", "edges"), "boolean[]", GRAPH, "low"),
    (3108, "minimum-cost-walk-in-weighted-graph", "minimumCost", ("n", "edges", "query"), "integer[]", GRAPH, "low"),
    (2421, "number-of-good-paths", "numberOfGoodPaths", ("vals", "edges"), "integer", GRAPH, "medium"),
    (1697, "checking-existence-of-edge-length-limited-paths", "distanceLimitedPathsExist", ("n", "edgeList", "queries"), "boolean[]", GRAPH, "medium"),
    (1786, "number-of-restricted-paths-from-first-to-last-node", "countRestrictedPaths", ("n", "edges"), "integer", GRAPH, "medium"),
    (1970, "last-day-where-you-can-still-cross", "latestDayToCross", ("row", "col", "cells"), "integer", GRAPH, "high"),
    (1368, "minimum-cost-to-make-at-least-one-valid-path-in-a-grid", "minCost", ("grid",), "integer", GRAPH, "high"),
    (2203, "minimum-weighted-subgraph-with-the-required-paths", "minimumWeight", ("n", "edges", "src1", "src2", "dest"), "long", GRAPH, "low"),
    (3117, "minimum-sum-of-values-by-dividing-array", "minimumValueSum", ("nums", "andValues"), "integer", DP, "low"),
    (3077, "maximum-strength-of-k-disjoint-subarrays", "maximumStrength", ("nums", "k"), "long", DP, "low"),
    (2188, "minimum-time-to-finish-the-race", "minimumFinishTime", ("tires", "changeTime", "numLaps"), "integer", DP, "medium"),
    (2809, "minimum-time-to-make-array-sum-at-most-x", "minimumTime", ("nums1", "nums2", "x"), "integer", DP, "low"),
    (2478, "number-of-beautiful-partitions", "beautifulPartitions", ("s", "k", "minLength"), "integer", DP, "medium"),
    (2719, "count-of-integers", "count", ("num1", "num2", "min_sum", "max_sum"), "integer", DP, "medium"),
    (2945, "find-maximum-non-decreasing-array-length", "findMaximumLength", ("nums",), "integer", DP, "low"),
    (2926, "maximum-balanced-subsequence-sum", "maxBalancedSubsequenceSum", ("nums",), "long", DP, "low"),
    (2035, "partition-array-into-two-arrays-to-minimize-sum-difference", "minimumDifference", ("nums",), "integer", DP, "high"),
    (1547, "minimum-cost-to-cut-a-stick", "minCost", ("n", "cuts"), "integer", DP, "high"),
    (2071, "maximum-number-of-tasks-you-can-assign", "maxTaskAssign", ("tasks", "workers", "pills", "strength"), "integer", GREEDY, "medium"),
    (1851, "minimum-interval-to-include-each-query", "minInterval", ("intervals", "queries"), "integer[]", GREEDY, "high"),
    (2940, "find-building-where-alice-and-bob-can-meet", "leftmostBuildingQueries", ("heights", "queries"), "integer[]", GREEDY, "low"),
    (3072, "distribute-elements-into-two-arrays-ii", "resultArray", ("nums",), "integer[]", GREEDY, "low"),
    (2366, "minimum-replacements-to-sort-the-array", "minimumReplacement", ("nums",), "long", GREEDY, "medium"),
    (3102, "minimize-manhattan-distances", "minimumDistance", ("points",), "integer", GREEDY, "low"),
    (3116, "kth-smallest-amount-with-single-denomination-combination", "findKthSmallest", ("coins", "k"), "long", GREEDY, "low"),
    (1611, "minimum-one-bit-operations-to-make-integers-zero", "minimumOneBitOperations", ("n",), "integer", BITS, "high"),
    (1896, "minimum-cost-to-change-the-final-value-of-expression", "minOperationsToFlip", ("expression",), "integer", BITS, "medium"),
    (995, "minimum-number-of-k-consecutive-bit-flips", "minKBitFlips", ("nums", "k"), "integer", BITS, "high"),
    (3022, "minimize-or-of-remaining-elements-using-operations", "minOrAfterOperations", ("nums", "k"), "integer", BITS, "low"),
    (3045, "count-prefix-and-suffix-pairs-ii", "countPrefixSuffixPairs", ("words",), "long", BITS, "low"),
    (761, "special-binary-string", "makeLargestSpecial", ("s",), "string", BITS, "high"),
)


def problem_id(frontend_id: int, slug: str) -> str:
    return f"lc-{frontend_id:04d}-{slug}"


def records() -> tuple[dict[str, object], ...]:
    return tuple({
        "frontend_id": frontend_id,
        "problem_id": problem_id(frontend_id, slug),
        "slug": slug,
        "entrypoint": f"Solution.{method}",
        "method": method,
        "parameters": parameters,
        "return_type": return_type,
        "topic": topic,
        "memorization_risk": risk,
        "comparison": "exact",
    } for frontend_id, slug, method, parameters, return_type, topic, risk in PROBLEMS)
