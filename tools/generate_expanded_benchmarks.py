from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.expanded_benchmark_catalog import records
from tools.expanded_benchmark_specs import CONSTRAINTS, PARAMETER_TYPES, SPECS
SEED = 20260718
MODULE_BY_TOPIC = {
    "graph_connectivity": "expanded_graph.py",
    "dynamic_programming_optimization": "expanded_dp.py",
    "greedy_offline_data_structures": "expanded_misc.py",
    "bit_string_expression": "expanded_misc.py",
}
REFERENCE_NAMES = {
    3123: "find_answer_reference", 3108: "minimum_cost_walk_reference",
    2421: "number_of_good_paths_reference", 1697: "distance_limited_reference",
    1786: "count_restricted_paths_reference", 1970: "latest_day_reference",
    1368: "min_grid_cost_reference", 2203: "minimum_weight_reference",
    3117: "minimum_value_sum_reference", 3077: "maximum_strength_reference",
    2188: "minimum_finish_time_reference", 2809: "minimum_time_reference",
    2478: "beautiful_partitions_reference", 2719: "count_integers_reference",
    2945: "maximum_nondecreasing_length_reference", 2926: "max_balanced_sum_reference",
    2035: "minimum_difference_reference", 1547: "minimum_cut_cost_reference",
    2071: "max_task_assign_reference", 1851: "min_interval_reference",
    2940: "leftmost_building_reference", 3072: "result_array_reference",
    2366: "minimum_replacement_reference", 3102: "minimum_manhattan_reference",
    3116: "kth_amount_reference", 1611: "minimum_one_bit_reference",
    1896: "expression_flip_reference", 995: "min_k_flips_reference",
    3022: "min_or_reference", 3045: "prefix_suffix_reference",
    761: "largest_special_reference",
}


def _dump(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def _title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.split("-"))


def _hidden_args(problem: int) -> list[list[object]]:
    # Fixed boundary/adversarial cases; no RNG is consumed during generation.
    cases = {
        3123: [[2, [[0, 1, 9]]], [4, [[0, 1, 1], [1, 3, 1], [0, 2, 1], [2, 3, 1], [1, 2, 10]]]],
        3108: [[2, [[0, 1, 0]], [[0, 1]]], [4, [[0, 1, 15], [1, 2, 7], [2, 3, 3]], [[0, 3], [0, 2], [1, 3]]]],
        2421: [[[7], []], [[2, 2, 2, 2], [[0, 1], [1, 2], [2, 3]]]],
        1697: [[2, [[0, 1, 5]], [[0, 1, 5], [0, 1, 6]]], [5, [[0, 1, 2], [1, 2, 2], [3, 4, 1]], [[0, 2, 3], [0, 4, 99]]]],
        1786: [[2, [[1, 2, 8]]], [4, [[1, 2, 1], [2, 4, 3], [1, 3, 1], [3, 4, 3], [2, 3, 1]]]],
        1970: [[1, 1, [[1, 1]]], [2, 3, [[1, 2], [2, 2], [1, 1], [2, 1], [1, 3], [2, 3]]]],
        1368: [[[[1]]], [[[2, 2, 2], [1, 1, 1], [4, 4, 4]]]],
        2203: [[3, [[0, 1, 1]], 0, 1, 2], [4, [[0, 2, 4], [1, 2, 2], [2, 3, 1], [0, 3, 20]], 0, 1, 3]],
        3117: [[[7], [7]], [[7, 3, 3], [3, 3]]],
        3077: [[[5], 1], [[4, -5, 4, -5, 4], 3]],
        2188: [[[[5, 2]], 100, 1], [[[2, 2], [3, 2]], 1, 6]],
        2809: [[[0], [0], 0], [[10, 10, 10], [1, 2, 3], 5]],
        2478: [["21", 1, 2], ["222222", 2, 2]],
        2719: [["1", "1", 1, 1], ["95", "105", 5, 6]],
        2945: [[[9]], [[9, 1, 1, 1, 20]]],
        2926: [[[-9]], [[5, 1, 7, 3, 10]]],
        2035: [[[1, 2]], [[2, -1, 0, 4, -2, 3]]],
        1547: [[2, [1]], [100, [1, 2, 50, 98, 99]]],
        2071: [[[1], [1], 0, 0], [[10, 10, 10], [1, 2, 3], 2, 8]],
        1851: [[[[1, 1]], [1, 2]], [[[1, 100], [50, 50], [49, 51]], [49, 50, 51, 100]]],
        2940: [[[5], [[0, 0]]], [[5, 1, 5, 6], [[0, 2], [1, 2], [3, 0]]]],
        3072: [[[1, 1, 1]], [[4, 3, 2, 1, 5, 5]]],
        2366: [[[1]], [[100, 1, 1]]],
        3102: [[[[0, 0], [0, 0], [0, 0]]], [[[0, 0], [10, 0], [0, 10], [10, 10]]]],
        3116: [[[1], 100], [[4, 6], 8]],
        1611: [[0], [1023]],
        1896: [["0"], ["(1|0)&(1|1)"]],
        995: [[[1], 1], [[0, 0, 0, 1, 0, 1, 1, 0], 3]],
        3022: [[[0], 0], [[15, 7, 3, 1], 3]],
        3045: [[ ["a"]], [["x", "x", "xx", "x"]]],
        761: [["10"], ["111000"]],
    }
    result = copy.deepcopy(cases[problem])
    rng = random.Random(SEED + problem)
    seen = {json.dumps(item, sort_keys=True) for item in result}
    while len(result) < 12:
        item = _random_small_args(problem, rng)
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _random_small_args(problem: int, rng: random.Random) -> list[object]:
    if problem in {3123, 1697, 1786}:
        n = rng.randint(2, 8)
        if problem == 1786:
            edges = [[i + 1, rng.randrange(i) + 1, rng.randint(1, 12)] for i in range(1, n)]
            for _ in range(rng.randint(0, 5)):
                a, b = rng.sample(range(1, n + 1), 2); edges.append([a, b, rng.randint(1, 12)])
            return [n, edges]
        edges = []
        for _ in range(rng.randint(1, 14)):
            a, b = rng.sample(range(n), 2); edges.append([a, b, rng.randint(1, 15)])
        if problem == 3123:
            unique = {}
            for a, b, w in edges: unique[min(a, b), max(a, b)] = [a, b, w]
            return [n, list(unique.values())]
        queries = [[*rng.sample(range(n), 2), rng.randint(1, 17)] for _ in range(rng.randint(1, 12))]
        return [n, edges, queries]
    if problem == 3108:
        n = rng.randint(2, 8)
        edges = [[*rng.sample(range(n), 2), rng.randrange(32)] for _ in range(rng.randint(0, 14))]
        queries = [rng.sample(range(n), 2) for _ in range(rng.randint(1, 12))]
        return [n, edges, queries]
    if problem == 2421:
        n = rng.randint(1, 9)
        return [[rng.randrange(5) for _ in range(n)], [[i, rng.randrange(i)] for i in range(1, n)]]
    if problem == 1970:
        row, col = rng.randint(1, 4), rng.randint(1, 4)
        cells = [[r, c] for r in range(1, row + 1) for c in range(1, col + 1)]
        rng.shuffle(cells); return [row, col, cells]
    if problem == 1368:
        rows, cols = rng.randint(1, 5), rng.randint(1, 5)
        return [[[rng.randint(1, 4) for _ in range(cols)] for _ in range(rows)]]
    if problem == 2203:
        n = rng.randint(3, 8); src1, src2, dest = rng.sample(range(n), 3)
        edges = [[*rng.sample(range(n), 2), rng.randint(1, 15)] for _ in range(rng.randint(1, 20))]
        return [n, edges, src1, src2, dest]
    if problem == 3117:
        n = rng.randint(1, 8); nums = [rng.randint(0, 31) for _ in range(n)]
        return [nums, [rng.randint(0, 31) for _ in range(rng.randint(1, min(4, n)))]]
    if problem == 3077:
        n = rng.randint(1, 8); choices = list(range(1, n + 1, 2))
        return [[rng.randint(-9, 9) for _ in range(n)], rng.choice(choices)]
    if problem == 2188:
        tires = [[rng.randint(1, 9), rng.randint(2, 5)] for _ in range(rng.randint(1, 4))]
        return [tires, rng.randint(1, 10), rng.randint(1, 8)]
    if problem == 2809:
        n = rng.randint(1, 7)
        return [[rng.randint(0, 9) for _ in range(n)], [rng.randint(0, 6) for _ in range(n)], rng.randint(0, 70)]
    if problem == 2478:
        n = rng.randint(1, 12)
        return ["".join(str(rng.randint(1, 9)) for _ in range(n)), rng.randint(1, min(4, n)), rng.randint(1, n)]
    if problem == 2719:
        low = rng.randint(1, 700); high = rng.randint(low, 1200)
        minimum = rng.randint(1, 20); return [str(low), str(high), minimum, rng.randint(minimum, 30)]
    if problem in {2945, 2926, 2366}:
        n = rng.randint(1, 10)
        if problem == 2926: return [[rng.randint(-15, 15) for _ in range(n)]]
        return [[rng.randint(1, 20) for _ in range(n)]]
    if problem == 2035:
        return [[rng.randint(-25, 25) for _ in range(2 * rng.randint(1, 7))]]
    if problem == 1547:
        n = rng.randint(2, 20); population = list(range(1, n)); rng.shuffle(population)
        return [n, population[:rng.randint(1, min(7, n - 1))]]
    if problem == 2071:
        tasks = [rng.randrange(12) for _ in range(rng.randint(1, 7))]
        workers = [rng.randrange(12) for _ in range(rng.randint(1, 7))]
        return [tasks, workers, rng.randint(0, len(workers)), rng.randint(0, 7)]
    if problem == 1851:
        intervals = []
        for _ in range(rng.randint(1, 10)):
            left = rng.randint(1, 18); intervals.append([left, rng.randint(left, 22)])
        return [intervals, [rng.randint(1, 22) for _ in range(rng.randint(1, 12))]]
    if problem == 2940:
        heights = [rng.randint(1, 18) for _ in range(rng.randint(1, 12))]
        return [heights, [[rng.randrange(len(heights)), rng.randrange(len(heights))] for _ in range(rng.randint(1, 15))]]
    if problem == 3072:
        return [[rng.randint(1, 20) for _ in range(rng.randint(3, 12))]]
    if problem == 3102:
        return [[[rng.randint(-20, 20), rng.randint(-20, 20)] for _ in range(rng.randint(3, 9))]]
    if problem == 3116:
        return [rng.sample(range(1, 20), rng.randint(1, 7)), rng.randint(1, 100)]
    if problem == 1611:
        return [rng.randrange(2048)]
    if problem == 1896:
        expression = rng.choice("01")
        for _ in range(rng.randint(1, 7)):
            atom = rng.choice("01"); op = rng.choice("&|")
            expression = f"({expression}{op}{atom})" if rng.random() < .7 else expression + op + atom
        return [expression]
    if problem == 995:
        n = rng.randint(1, 10)
        return [[rng.randrange(2) for _ in range(n)], rng.randint(1, n)]
    if problem == 3022:
        n = rng.randint(1, 9)
        return [[rng.randrange(64) for _ in range(n)], rng.randrange(n)]
    if problem == 3045:
        words = ["".join(rng.choice("abc") for _ in range(rng.randint(1, 7))) for _ in range(rng.randint(1, 15))]
        return [words]
    if problem == 761:
        parts = ["1" * rng.randint(1, 5) + "0" * rng.randint(1, 5) for _ in range(3)]
        # Concatenations of primitive 1^m0^m blocks are special.
        return ["".join("1" * len(part.strip("0")) + "0" * len(part.strip("0")) for part in parts)]
    raise KeyError(problem)


def _stress_args(problem: int) -> list[object]:
    if problem == 3123:
        return [50_000, [[i, i + 1, 1] for i in range(49_999)]]
    if problem == 3108:
        return [50_001, [[i, i + 1, (i * 17) & 65535] for i in range(50_000)],
                [[0, 50_000]] + [[i, i + 1] for i in range(50_000)]]
    if problem == 2421:
        return [[i % 97 for i in range(30_000)], [[i - 1, i] for i in range(1, 30_000)]]
    if problem == 1697:
        return [50_001, [[i, i + 1, i + 1] for i in range(50_000)],
                [[0, 50_000, 50_001] for _ in range(50_000)]]
    if problem == 1786:
        return [20_000, [[i, i + 1, 1] for i in range(1, 20_000)]]
    if problem == 1970:
        return [100, 200, [[r + 1, c + 1] for r in range(100) for c in range(200)]]
    if problem == 1368:
        return [[[1 + (r + c) % 4 for c in range(100)] for r in range(100)]]
    if problem == 2203:
        return [100_000, [[i, i + 1, 1] for i in range(99_999)] + [[1, 0, 1]], 0, 1, 99_999]
    if problem == 3117:
        return [[65535 - (i % 4) for i in range(10_000)], [65532] * 10]
    if problem == 3077:
        return [[(i % 101) - 50 for i in range(2000)], 499]
    if problem == 2188:
        return [[[i + 1, 2 + i % 5] for i in range(2000)], 100_000, 1000]
    if problem == 2809:
        return [[i % 1001 for i in range(1000)], [(i * 7) % 1001 for i in range(1000)], 250_000]
    if problem == 2478:
        return ["21" * 500, 100, 2]
    if problem == 2719:
        return ["1", "9" * 22, 1, 198]
    if problem == 2945:
        return [[1 + i % 100_000 for i in range(100_000)]]
    if problem == 2926:
        return [[((i * 1000003) % 2_000_000_001) - 1_000_000_000 for i in range(100_000)]]
    if problem == 2035:
        return [[(i * 99991) % 20_000_001 - 10_000_000 for i in range(30)]]
    if problem == 1547:
        return [1_000_000, [i * 9900 + 1 for i in range(1, 101)]]
    if problem == 2071:
        return [[i % 1_000_000 for i in range(50_000)], [(i * 3) % 1_000_000 for i in range(50_000)], 25_000, 100_000]
    if problem == 1851:
        return [[[i, i + 1000] for i in range(100_000)], [i for i in range(100_000)]]
    if problem == 2940:
        return [[i % 1000 for i in range(50_000)], [[i, 49_999 - i] for i in range(50_000)]]
    if problem == 3072:
        return [[(i * 48271) % 1_000_000_007 for i in range(100_000)]]
    if problem == 2366:
        return [[1_000_000_000 - i * 9973 for i in range(100_000)]]
    if problem == 3102:
        return [[[i, (i * 99991) % 100_000_000] for i in range(100_000)]]
    if problem == 3116:
        return [[2, 3, 5, 7, 11, 13, 17, 19, 23], 2_000_000_000]
    if problem == 1611:
        return [1_000_000_000]
    if problem == 1896:
        return ["|".join("1" for _ in range(50_000))]
    if problem == 995:
        return [[(i * 17) & 1 for i in range(100_000)], 499]
    if problem == 3022:
        return [[(i * 48271) & ((1 << 30) - 1) for i in range(100_000)], 50_000]
    if problem == 3045:
        return [["a" * (1 + i % 20) for i in range(25_000)]]
    if problem == 761:
        return ["1" * 25 + "0" * 25]
    raise KeyError(problem)


def _stress_variants(problem: int) -> list[list[object]]:
    base = _stress_args(problem)
    if problem == 1611:
        return [base, [1 << 29], [(1 << 30) - 1]]
    if problem == 1896:
        return [base,
                ["&".join("0" for _ in range(50_000))],
                ["(" * 20_000 + "1" + "|0)" * 20_000]]
    if problem == 2719:
        return [base, ["1" + "0" * 21, "8" + "9" * 21, 100, 250],
                ["9" * 21, "9" * 22, 150, 300]]
    if problem == 2478:
        return [base, ["26" * 500, 125, 2], ["21" * 500, 1, 1000]]
    if problem == 761:
        return [base, ["10" * 25], ["1" * 24 + "0" * 24]]
    if problem == 995:
        return [base, [[1, 0, 0, 1] * 25_000, 500], [[0] * 100_000, 500]]

    def reorder(value: object, rotate: bool) -> object:
        copied = copy.deepcopy(value)
        if not isinstance(copied, list) or len(copied) < 2:
            return copied
        if rotate:
            middle = 1
            return copied[middle:] + copied[:middle]
        return list(reversed(copied))

    reversed_args = [reorder(value, False) for value in base]
    rotated_args = [reorder(value, True) for value in base]
    return [base, reversed_args, rotated_args]


def _wrapper(method: str, parameters: tuple[str, ...], reference: str) -> str:
    signature = ", ".join(parameters)
    return (f"\n\nclass Solution:\n"
            f"    def {method}(self, {signature}):\n"
            f"        return {reference}({signature})\n")


def _mutant_wrapper(method: str, parameters: tuple[str, ...], reference: str,
                    mode: str) -> str:
    signature = ", ".join(parameters)
    corrupt = {
        "boundary": "return [] if isinstance(answer, list) else (\"\" if isinstance(answer, str) else 0)",
        "off_by_one": "return [not x if isinstance(x, bool) else x + 1 for x in answer] if isinstance(answer, list) else (answer[::-1] if isinstance(answer, str) else answer + 1)",
        "direction": "return list(reversed(answer)) if isinstance(answer, list) else (answer[:-1] if isinstance(answer, str) else -answer)",
    }[mode]
    return (f"\n\nclass Solution:\n"
            f"    def {method}(self, {signature}):\n"
            f"        answer = {reference}({signature})\n"
            f"        {corrupt}\n")


def generate(output_root: Path) -> None:
    oracle_root = ROOT / "src" / "ffjudge" / "oracles"
    for record in records():
        frontend_id = int(record["frontend_id"])
        reference, _brute, examples, description = SPECS[frontend_id]
        directory = output_root / str(record["problem_id"])
        directory.mkdir(parents=True, exist_ok=True)
        role_prefix = "hard" if frontend_id not in {995, 1368, 1547, 1611, 1851, 1970} else "medium"
        problem = {
            "problem_id": record["problem_id"],
            "title": _title(str(record["slug"])),
            "difficulty": "hard",
            "role": f"{role_prefix}_{record['topic']}_candidate",
            "source_url": f"https://leetcode.com/problems/{record['slug']}/",
            "description": description + " Inputs use Python lists and integers; unless explicitly stated, callers need not preserve mutable inputs.",
            "input_contract": (f"Parameters in order: {PARAMETER_TYPES[frontend_id]}. "
                               + CONSTRAINTS[frontend_id]),
            "output_contract": f"Return {record['return_type']} using exact comparison. Python integer arithmetic has no 32-bit overflow; array/query order is significant.",
            "entrypoint": {"kind": "class_method", "class_name": "Solution", "method": record["method"]},
            "comparison": "exact",
            "limits": {"time_seconds": 4.0, "memory_mb": 256, "cpus": 1.0, "pids": 32},
        }
        metadata = {
            "problem_id": record["problem_id"],
            "topic": record["topic"],
            "memorization_risk": record["memorization_risk"],
            "generator_seed": SEED,
            "formal_generator": "tools/generate_expanded_benchmarks.py",
        }
        public = [{"args": args, "expected": reference(*copy.deepcopy(args))} for args in examples]
        hidden_args = _hidden_args(frontend_id)
        hidden = [{"args": args, "expected": reference(*copy.deepcopy(args))} for args in hidden_args]
        stress = [{"args": args,
                   "expected": reference(*copy.deepcopy(args))}
                  for args in _stress_variants(frontend_id)]
        module = (oracle_root / MODULE_BY_TOPIC[str(record["topic"])]).read_text(encoding="utf-8")
        reference_name = REFERENCE_NAMES[frontend_id]
        accepted = module + _wrapper(str(record["method"]), tuple(record["parameters"]), reference_name)
        files: dict[str, bytes] = {
            "problem.json": _dump(problem),
            "benchmark_metadata.json": _dump(metadata),
            "public_tests.json": _dump(public),
            "hidden_tests.json": _dump(hidden),
            "stress_tests.json": _dump(stress),
            "accepted.py": accepted.encode(),
            "mutants.json": _dump({
                "wrong_boundary.py": "wrong initialization/minimum boundary",
                "wrong_off_by_one.py": "count or query boundary off by one",
                "wrong_direction.py": "wrong ordering/direction/sign",
            }),
        }
        for mode in ("boundary", "off_by_one", "direction"):
            files[f"wrong_{mode}.py"] = (module + _mutant_wrapper(
                str(record["method"]), tuple(record["parameters"]), reference_name, mode)).encode()
        for name, payload in files.items():
            (directory / name).write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic expanded benchmark fixtures")
    parser.add_argument("--output-root", type=Path, default=ROOT / "examples")
    args = parser.parse_args()
    generate(args.output_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
