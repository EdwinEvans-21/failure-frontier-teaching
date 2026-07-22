from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ffjudge.oracles.problem_bank_v4_calibration import (
    cherry_pickup_reference,
    critical_edges_reference,
    count_routes_reference,
    max_dot_product_reference,
    kth_smallest_sum_reference,
    paint_house_reference,
    pizza_ways_reference,
    maximum_requests_reference,
    minimum_days_reference,
    remove_edges_reference,
    parallel_courses_reference,
    stone_game_v_reference,
    strange_printer_ii_reference,
    string_compression_reference,
)
from src.ffjudge.oracles.expanded_dp import minimum_cut_cost_bruteforce, minimum_cut_cost_reference

SEED = 20260720
CALIBRATION = (1563, 1575, 1579, 1591, 1601)
STALENESS = (1707, 1982)


def dump(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def safe_rmtree(path: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        raise ValueError(f"refusing to delete outside output root: {resolved_path}")
    if path.exists():
        shutil.rmtree(path)


def cleanup_stale_directories(output_root: Path) -> None:
    for number in STALENESS:
        for path in output_root.glob(f"lc-{number}-*"):
            safe_rmtree(path, output_root)


def connected_graph(rng: random.Random, n: int, extra: int) -> list[list[int]]:
    pairs: set[tuple[int, int]] = set()
    edges: list[list[int]] = []
    for node in range(1, n):
        other = rng.randrange(node)
        pairs.add((other, node))
        edges.append([other, node, rng.randint(1, 9)])
    candidates = [
        (a, b)
        for a in range(n)
        for b in range(a + 1, n)
        if (a, b) not in pairs
    ]
    rng.shuffle(candidates)
    for a, b in candidates[:extra]:
        edges.append([a, b, rng.randint(1, 9)])
    return edges


def cases(number: int, count: int, offset: int = 0) -> list[list[object]]:
    rng = random.Random(SEED + number + offset)
    result: list[list[object]] = []
    if number == 1489:
        result.extend([
            [2, [[0, 1, 1]]],
            [4, [[0, 1, 1], [1, 2, 1], [2, 3, 1], [0, 3, 1]]],
            [5, [[0, 1, 1], [1, 2, 1], [2, 3, 2], [0, 3, 2], [0, 4, 3], [3, 4, 3], [1, 4, 6]]],
            [3, [[0, 1, 1], [1, 2, 2], [0, 2, 3]]],
            [4, [[0, 1, 2], [1, 2, 2], [2, 3, 2], [0, 3, 2], [0, 2, 2], [1, 3, 2]]],
        ])
        while len(result) < count:
            n = rng.randint(2, 7)
            edges = connected_graph(rng, n, rng.randint(0, min(6, n * (n - 1) // 2 - n + 1)))
            result.append([n, edges])
    elif number == 1494:
        result.extend([
            [4, [[2, 1], [3, 1], [1, 4]], 2],
            [5, [[2, 1], [3, 1], [4, 1], [1, 5]], 2],
            [3, [], 2],
            [4, [[1, 2], [2, 3], [3, 4]], 1],
            [4, [[1, 2], [2, 3], [1, 3]], 3],
        ])
        while len(result) < count:
            n = rng.randint(1, 6)
            relations = []
            for course in range(2, n + 1):
                for prev in range(1, course):
                    if rng.random() < 0.3:
                        relations.append([prev, course])
            result.append([n, relations, rng.randint(1, max(1, n))])
    elif number == 1531:
        result.extend([
            ["aaabcccd", 2],
            ["aabbaa", 2],
            ["aaaaaaaaaaa", 0],
            ["abcdef", 2],
            ["abababab", 3],
        ])
        while len(result) < count:
            length = rng.randint(1, 8)
            s = "".join(rng.choice("abcde") for _ in range(length))
            result.append([s, rng.randint(0, min(4, length))])
    elif number == 1547:
        result.extend([
            [7, [1, 3, 4, 5]],
            [9, [5, 6, 1, 4, 2]],
            [10, [2, 4, 7]],
            [20, [1, 10, 12, 14]],
            [5, [1, 2, 3, 4]],
        ])
        while len(result) < count:
            n = rng.randint(2, 12)
            cuts = sorted(rng.sample(range(1, n), rng.randint(1, min(5, n - 1))))
            result.append([n, cuts])
    elif number == 1553:
        result.extend([
            [1],
            [6],
            [10],
            [56],
            [100],
        ])
        while len(result) < count:
            result.append([rng.randint(1, 1000000000)])
    elif number == 1563:
        result.extend([
            [[6, 2, 3, 4, 5, 6, 7]],
            [[7, 1, 2, 3, 4, 5, 6, 7]],
            [[4, 7, 2, 9, 4]],
            [[8, 10, 2, 8, 2, 8, 10, 2]],
            [[3, 4]],
        ])
        while len(result) < count:
            length = rng.randint(2, 8)
            result.append([[rng.randint(1, 10) for _ in range(length)]])
    elif number == 1575:
        result.extend([
            [[2, 3, 6, 8, 12], 0, 4, 6],
            [[4, 7, 9, 10], 1, 3, 5],
            [[1, 2, 4], 0, 2, 3],
            [[0, 1, 3, 6, 10], 0, 4, 7],
            [[1, 5, 10, 15], 1, 2, 10],
        ])
        while len(result) < count:
            length = rng.randint(2, 6)
            locations = sorted(rng.sample(range(0, 20), length))
            start = rng.randrange(length)
            finish = rng.randrange(length)
            fuel = rng.randint(0, 12)
            result.append([locations, start, finish, fuel])
    elif number == 1579:
        result.extend([
            [4, [[3, 1, 2], [3, 2, 2], [1, 1, 3], [2, 2, 3], [1, 2, 1], [1, 3, 1], [2, 3, 1]]],
            [4, [[3, 1, 1], [3, 2, 1], [3, 4, 1], [1, 2, 2], [2, 4, 2], [1, 4, 3]]],
            [3, [[3, 1, 2], [3, 2, 2], [1, 2, 1], [2, 3, 1], [1, 3, 1]]],
            [5, [[3, 1, 1], [3, 2, 1], [3, 4, 1], [3, 5, 1], [1, 2, 2], [2, 3, 2], [4, 5, 2]]],
            [4, [[3, 1, 2], [3, 2, 2], [3, 3, 3], [1, 4, 1], [2, 4, 1], [1, 2, 1]]],
        ])
        while len(result) < count:
            n = rng.randint(2, 5)
            edges = []
            for _ in range(rng.randint(n, n + 4)):
                edge_type = rng.randint(1, 3)
                u, v = rng.sample(range(1, n + 1), 2)
                edges.append([edge_type, u, v])
            result.append([n, edges])
    elif number == 1591:
        result.extend([
            [[[1, 1, 1], [1, 2, 1], [1, 1, 1]]],
            [[[1, 2, 2], [1, 1, 2], [1, 1, 2]]],
            [[[1, 2, 3], [1, 3, 3], [1, 1, 3]]],
            [[[1, 1, 2], [2, 3, 2], [2, 3, 3]]],
            [[[1, 1], [1, 1]]],
        ])
        while len(result) < count:
            rows = rng.randint(1, 4)
            cols = rng.randint(1, 4)
            palette = [1, 2, 3]
            result.append([[[rng.choice(palette) for _ in range(cols)] for _ in range(rows)]])
    elif number == 1601:
        result.extend([
            [3, [[0, 1], [1, 2], [2, 0], [0, 2]]],
            [4, [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2], [1, 3]]],
            [2, [[0, 1], [1, 0], [0, 0], [1, 1]]],
            [3, [[0, 1], [1, 0], [1, 2], [2, 1], [0, 2], [2, 0]]],
            [2, [[0, 1], [1, 0], [0, 1], [1, 0], [0, 0]]],
        ])
        while len(result) < count:
            n = rng.randint(2, 5)
            requests = []
            for _ in range(rng.randint(n, n + 4)):
                u, v = rng.sample(range(n), 2)
                requests.append([u, v])
            result.append([n, requests])
    return result[:count]


def expected(number: int, args: list[object]) -> object:
    if number == 1489:
        return critical_edges_reference(*args)
    if number == 1494:
        return parallel_courses_reference(*args)
    if number == 1531:
        return string_compression_reference(*args)
    if number == 1547:
        return minimum_cut_cost_reference(*args)
    if number == 1553:
        return minimum_days_reference(*args)
    if number == 1563:
        return stone_game_v_reference(args[0])
    if number == 1575:
        return count_routes_reference(*args)
    if number == 1579:
        return remove_edges_reference(*args)
    if number == 1591:
        return strange_printer_ii_reference(args[0])
    if number == 1601:
        return maximum_requests_reference(*args)
    raise KeyError(number)


def records(number: int, raw: list[list[object]]) -> list[dict[str, object]]:
    return [{"args": args, "expected": expected(number, args)} for args in raw]


def source(number: int, mutant: int | None = None) -> str:
    module = (ROOT / "src/ffjudge/oracles/problem_bank_v4_calibration.py").read_text(encoding="utf-8")
    if number == 1547:
        module = module.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\n"
            "from src.ffjudge.oracles.expanded_dp import "
            "minimum_cut_cost_bruteforce, minimum_cut_cost_reference\n\n",
            1,
        )
    wrappers = {
        1489: "class Solution:\n    def findCriticalAndPseudoCriticalEdges(self, n, edges):\n        return critical_edges_reference(n, edges)\n",
        1494: "class Solution:\n    def minNumberOfSemesters(self, n, relations, k):\n        return parallel_courses_reference(n, relations, k)\n",
        1531: "class Solution:\n    def getLengthOfOptimalCompression(self, s, k):\n        return string_compression_reference(s, k)\n",
        1547: "class Solution:\n    def minCost(self, n, cuts):\n        return minimum_cut_cost_reference(n, cuts)\n",
        1553: "class Solution:\n    def minDays(self, n):\n        return minimum_days_reference(n)\n",
        1563: "class Solution:\n    def stoneGameV(self, stoneValue):\n        return stone_game_v_reference(stoneValue)\n",
        1575: "class Solution:\n    def countRoutes(self, locations, start, finish, fuel):\n        return count_routes_reference(locations, start, finish, fuel)\n",
        1579: "class Solution:\n    def maxNumEdgesToRemove(self, n, edges):\n        return remove_edges_reference(n, edges)\n",
        1591: "class Solution:\n    def isPrintable(self, targetGrid):\n        return strange_printer_ii_reference(targetGrid)\n",
        1601: "class Solution:\n    def maximumRequests(self, n, requests):\n        return maximum_requests_reference(n, requests)\n",
    }
    if mutant is None:
        wrapper = wrappers[number]
    else:
        wrong = {
            1489: ["return [[], []]", "return [list(range(len(edges))), []]", "return [[], list(range(len(edges)))]", "return critical_edges_reference(n, edges)[::-1]", "return [critical_edges_reference(n, edges)[0], []]"],
            1494: ["return 0", "return n", "return parallel_courses_reference(n, relations, max(1, k - 1))", "return parallel_courses_reference(n, relations, k) + 1", "return parallel_courses_reference(n, relations[:-1], k)"],
            1531: ["return 0", "return 1", "return string_compression_reference(s, max(0, k - 1))", "return string_compression_reference(s, k) - 1", "return string_compression_reference(s, k) + 1"],
            1547: ["return 0", "return minimum_cut_cost_reference(n, cuts[:-1])", "return minimum_cut_cost_reference(n, cuts[:-1]) + 1", "return minimum_cut_cost_reference(n, cuts) + 1", "return min(cuts) if cuts else 0"],
            1553: ["return 0", "return n", "return minimum_days_reference(n - 1) if n > 0 else 0", "return minimum_days_reference(n) + 1", "return minimum_days_reference(max(1, n // 2))"],
            1563: ["return 0", "return sum(stoneValue)", "return stone_game_v_reference(stoneValue[:-1])", "return stone_game_v_reference(stoneValue[:-1]) + 1", "return stone_game_v_reference(stoneValue) + 1"],
            1575: ["return 0", "return 1", "return count_routes_reference(locations, start, finish, max(0, fuel - 1))", "return count_routes_reference(locations[::-1], start, finish, fuel)", "return count_routes_reference(locations, start, finish, fuel) + 1"],
            1579: ["return 0", "return len(edges)", "return remove_edges_reference(n, edges[:-1])", "return remove_edges_reference(n, edges) + 1", "return remove_edges_reference(n, edges[:-1]) + 1"],
            1591: ["return True", "return False", "return strange_printer_ii_reference(targetGrid[::-1])", "return not strange_printer_ii_reference(targetGrid)", "return True if strange_printer_ii_reference(targetGrid) else False"],
            1601: ["return 0", "return len(requests)", "return maximum_requests_reference(n, requests[:-1])", "return maximum_requests_reference(n, requests) + 1", "return maximum_requests_reference(n, requests[:-1]) + 1"],
        }[number][mutant]
        method = {
            1489: "findCriticalAndPseudoCriticalEdges(self, n, edges)",
            1494: "minNumberOfSemesters(self, n, relations, k)",
            1531: "getLengthOfOptimalCompression(self, s, k)",
            1547: "minCost(self, n, cuts)",
            1553: "minDays(self, n)",
            1563: "stoneGameV(self, stoneValue)",
            1575: "countRoutes(self, locations, start, finish, fuel)",
            1579: "maxNumEdgesToRemove(self, n, edges)",
            1591: "isPrintable(self, targetGrid)",
            1601: "maximumRequests(self, n, requests)",
        }[number]
        wrapper = f"class Solution:\n    def {method}:\n        {wrong}\n"
    return module + "\n\n" + wrapper


def specs() -> dict[int, dict[str, object]]:
    return {
        1489: {
            "slug": "find-critical-and-pseudo-critical-edges-in-minimum-spanning-tree",
            "title": "Find Critical and Pseudo-Critical Edges in Minimum Spanning Tree",
            "method": "findCriticalAndPseudoCriticalEdges",
            "comparison": "custom",
            "checker": "mst_edge_classification",
            "description": "Classify edges that are required or optional in some minimum spanning tree.",
            "input": "n is 2..100; edges are distinct undirected weighted pairs and the graph is connected.",
            "output": "Return [critical_indices, pseudo_critical_indices].",
            "family": "mst",
            "complexity": "O(E^2 alpha(V)) time, O(V+E) space",
        },
        1494: {
            "slug": "parallel-courses-ii",
            "title": "Parallel Courses II",
            "method": "minNumberOfSemesters",
            "comparison": "exact",
            "description": "Take at most k available courses per semester after their prerequisites are done.",
            "input": "1 <= n <= 15, relations describe prerequisite pairs, and 1 <= k <= n.",
            "output": "Return the minimum number of semesters. Exact integer comparison.",
            "family": "bitmask_dp",
            "complexity": "O(2^n * n) time, O(2^n) space",
        },
        1531: {
            "slug": "string-compression-ii",
            "title": "String Compression II",
            "method": "getLengthOfOptimalCompression",
            "comparison": "exact",
            "description": "Delete at most k characters to minimize the run-length-encoded length.",
            "input": "1 <= len(s) <= 100; s consists of lowercase letters; 0 <= k <= len(s).",
            "output": "Return the minimum compressed length. Exact integer comparison.",
            "family": "string_dp",
            "complexity": "O(n^2 * k) time, O(nk) space",
        },
        1547: {
            "slug": "minimum-cost-to-cut-a-stick",
            "title": "Minimum Cost to Cut a Stick",
            "method": "minCost",
            "comparison": "exact",
            "description": "Cut the stick at all requested positions with minimum total cost.",
            "input": "2 <= n <= 1e6; cuts are distinct interior integer positions.",
            "output": "Return the minimum total cut cost. Exact integer comparison.",
            "family": "interval_dp",
            "complexity": "O(m^3) time, O(m^2) space",
        },
        1553: {
            "slug": "minimum-number-of-days-to-eat-n-oranges",
            "title": "Minimum Number of Days to Eat N Oranges",
            "method": "minDays",
            "comparison": "exact",
            "description": "Eat oranges using +1, /2, or /3 style operations with minimum days.",
            "input": "0 <= n <= 1e9.",
            "output": "Return the minimum days. Exact integer comparison.",
            "family": "memoized_dp",
            "complexity": "O(log n) expected recursive memoized time, O(log n) space",
        },
        1563: {
            "slug": "stone-game-v",
            "title": "Stone Game V",
            "method": "stoneGameV",
            "comparison": "exact",
            "description": "Split the array to maximize Alice's score under Stone Game V rules.",
            "input": "1 <= len(stoneValue) <= 20; values are positive integers.",
            "output": "Return the maximum achievable score. Exact integer comparison.",
            "family": "interval_dp",
            "complexity": "O(n^3) time, O(n^2) space",
        },
        1575: {
            "slug": "count-all-possible-routes",
            "title": "Count All Possible Routes",
            "method": "countRoutes",
            "comparison": "exact",
            "description": "Count routes from start to finish with limited fuel.",
            "input": "locations are distinct; 2 <= len(locations) <= 100; fuel is small in benchmark instances.",
            "output": "Return the number of routes modulo 1e9+7. Exact integer comparison.",
            "family": "memoized_dp",
            "complexity": "O(n^2 * fuel) time, O(n * fuel) space",
        },
        1579: {
            "slug": "remove-max-number-of-edges-to-keep-graph-fully-traversable",
            "title": "Remove Max Number of Edges to Keep Graph Fully Traversable",
            "method": "maxNumEdgesToRemove",
            "comparison": "exact",
            "description": "Remove as many edges as possible while keeping Alice and Bob connected.",
            "input": "n is small in benchmark instances; edges are type 1, 2, or 3.",
            "output": "Return the maximum number of removable edges or -1. Exact integer comparison.",
            "family": "graph_search",
            "complexity": "O(E alpha(V)) time on reference, exhaustive oracle for validation",
        },
        1591: {
            "slug": "strange-printer-ii",
            "title": "Strange Printer II",
            "method": "isPrintable",
            "comparison": "exact",
            "description": "Decide whether a target grid can be printed by layered rectangles.",
            "input": "Grid colors are small positive integers; benchmark grids are tiny.",
            "output": "Return a boolean. Exact comparison.",
            "family": "graph_toposort",
            "complexity": "O(RC + K^2) time, O(K^2) space",
        },
        1601: {
            "slug": "maximum-number-of-achievable-transfer-requests",
            "title": "Maximum Number of Achievable Transfer Requests",
            "method": "maximumRequests",
            "comparison": "exact",
            "description": "Choose the largest subset of requests with balanced in/out degree per building.",
            "input": "n is small in benchmark instances; requests are ordered pairs of buildings.",
            "output": "Return the maximum achievable request count. Exact integer comparison.",
            "family": "subset_search",
            "complexity": "O(2^m * n) time, O(n) space",
        },
    }


def stress(number: int) -> list[list[object]]:
    rng = random.Random(SEED + 9000 + number)
    if number == 1489:
        return [
            [4, [[0, 1, 1], [1, 2, 1], [2, 3, 1], [0, 3, 1]]],
            [5, [[0, 1, 1], [1, 2, 2], [2, 3, 2], [3, 4, 2], [0, 4, 3]]],
            [6, [[0, 1, 2], [1, 2, 2], [2, 3, 2], [3, 4, 3], [4, 5, 3], [0, 5, 10]]],
        ]
    if number == 1494:
        return [
            [4, [[2, 1], [3, 1], [1, 4]], 2],
            [5, [[2, 1], [3, 1], [4, 1], [1, 5]], 2],
            [6, [[1, 2], [1, 3], [3, 4], [4, 5], [2, 6]], 2],
        ]
    if number == 1531:
        return [["aaabcccd", 2], ["aabbaa", 2], ["aaaaaaaaaaa", 0]]
    if number == 1547:
        return [[7, [1, 3, 4, 5]], [9, [5, 6, 1, 4, 2]], [10, [2, 4, 7]]]
    if number == 1553:
        return [[1], [6], [56]]
    if number == 1563:
        return [[[1, 2, 3, 4]], [[5, 1, 2, 6, 1]], [[8, 2, 6, 1, 7, 3]]]
    if number == 1575:
        return [
            [[2, 3, 6, 8], 0, 3, 6],
            [[1, 5, 9, 14], 1, 3, 10],
            [[0, 2, 4, 6, 8], 2, 4, 8],
        ]
    if number == 1579:
        return [
            [4, [[3, 1, 1], [3, 2, 1], [3, 4, 1], [1, 2, 2], [2, 4, 2], [1, 4, 3]]],
            [3, [[3, 1, 2], [3, 2, 2], [1, 2, 1], [2, 3, 1], [1, 3, 1]]],
            [4, [[3, 1, 2], [3, 2, 2], [1, 4, 1], [2, 4, 1], [1, 2, 1]]],
        ]
    if number == 1591:
        return [
            [[[1, 1, 1], [1, 2, 1], [1, 1, 1]]],
            [[[1, 2, 2], [1, 1, 2], [1, 1, 2]]],
            [[[1, 1], [1, 1]]],
        ]
    if number == 1601:
        return [
            [3, [[0, 1], [1, 2], [2, 0], [0, 2]]],
            [4, [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2], [1, 3]]],
            [2, [[0, 1], [1, 0], [0, 0], [1, 1]]],
        ]
    return []


def cleanup_generated_dirs(output_root: Path) -> None:
    cleanup_stale_directories(output_root)


def generate(output_root: Path) -> None:
    cleanup_generated_dirs(output_root)
    metadata = specs()
    for number in CALIBRATION:
        spec = metadata[number]
        directory = output_root / f"lc-{number}-{spec['slug']}"
        problem = {
            "problem_id": directory.name,
            "title": spec["title"],
            "difficulty": "hard",
            "role": f"hard_{spec['family']}_candidate",
            "source_url": f"https://leetcode.com/problems/{spec['slug']}/",
            "description": spec["description"],
            "input_contract": spec["input"],
            "output_contract": spec["output"],
            "entrypoint": {"kind": "class_method", "class_name": "Solution", "method": spec["method"]},
            "comparison": spec["comparison"],
            "limits": {"time_seconds": 6.0, "memory_mb": 512, "cpus": 1.0, "pids": 32},
        }
        if "checker" in spec:
            problem["checker"] = spec["checker"]
        write(directory / "problem.json", dump(problem))
        write(directory / "benchmark_metadata.json", dump({
            "problem_id": directory.name,
            "topic": spec["family"],
            "generator_seed": SEED,
            "formal_generator": "tools/generate_problem_bank_v4_calibration.py",
            "reference_complexity": spec["complexity"],
            "oracle_version": "v4-calibration-2",
            "oracle_algorithm": {
                1489: "MST enumeration with edge forcing",
                1494: "subset DP over available courses",
                1531: "delete/keep recursion with run-length accounting",
                1547: "interval DP over cut positions",
                1553: "memoized integer reduction recursion",
                1563: "interval DP over all split points",
                1575: "memoized route-count recursion",
                1579: "typed connectivity preservation with DSU",
                1591: "rectangle dependency topological check",
                1601: "subset enumeration with balance constraints",
            }[number],
            "differential_target": 10000,
        }))
        write(directory / "public_tests.json", dump(records(number, cases(number, 5))))
        write(directory / "hidden_tests.json", dump(records(number, cases(number, 60, 100))))
        write(directory / "stress_tests.json", dump(records(number, stress(number))))
        write(directory / "accepted.py", source(number))
        mutant_map = {}
        for index in range(5):
            name = f"wrong_semantic_{index + 1}.py"
            write(directory / name, source(number, index))
            mutant_map[name] = f"semantic mutant {index + 1}"
        write(directory / "mutants.json", dump(mutant_map))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "examples")
    args = parser.parse_args()
    generate(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
