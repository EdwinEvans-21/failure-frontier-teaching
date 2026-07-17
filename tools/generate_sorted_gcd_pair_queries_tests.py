"""Regenerate deterministic formal tests for the LC 3312 fixture."""

from __future__ import annotations

import argparse
import json
from math import gcd
from pathlib import Path

from ffjudge.oracles.sorted_gcd_pair_queries import gcd_values_reference


ROOT = Path(__file__).parents[1] / "examples" / "sorted_gcd_pair_queries"


def case(nums: list[int], queries: list[int]) -> dict[str, object]:
    return {
        "args": [nums, queries],
        "expected": gcd_values_reference(nums, queries),
    }


def boundary_queries(nums: list[int]) -> list[int]:
    pairs = sorted(
        gcd(nums[left], nums[right])
        for left in range(len(nums))
        for right in range(left + 1, len(nums))
    )
    candidates = {0, len(pairs) - 1}
    for index in range(1, len(pairs)):
        if pairs[index - 1] != pairs[index]:
            candidates.update((index - 1, index, index + 1))
    return sorted(query for query in candidates if 0 <= query < len(pairs))


def write_cases(
    output_dir: Path, filename: str, cases: list[dict[str, object]]
) -> None:
    (output_dir / filename).write_text(
        json.dumps(cases, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    public = [
        case([2, 3, 4], [0, 2, 2]),
        case([4, 4, 2, 1], [5, 3, 1, 0]),
        case([2, 2], [0, 0]),
        case([6, 10, 15], [0, 1, 2]),
    ]

    boundary_nums = [6, 10, 12, 15, 18, 20, 24, 30]
    unordered_total = 8 * 7 // 2
    repeated_total = 12 * 11 // 2
    hidden = [
        case([2, 4], [0]),
        case([1] * 7, [0, 20, 7, 0]),
        case([36] * 9, [35, 0, 17]),
        case([6] * 40 + [10] * 35 + [15] * 25,
             [0, 4949, 779, 780, 2164, 2165]),
        case([2, 3, 5, 7, 11, 13, 17], [0, 20, 9]),
        case([8, 9, 25, 49, 121], [9, 0, 4]),
        case([1, 2, 4, 8, 16, 32, 64], [0, 5, 6, 14, 20]),
        case([6, 10, 14, 15, 21, 22, 33, 35],
             [0, 27, 3, 9, 18]),
        case([49_999, 49_991, 49_989, 50_000], [5, 0, 2]),
        case(boundary_nums, boundary_queries(boundary_nums)),
        case([9, 12, 15, 18, 21], [0, 9]),
        case([12, 18, 24, 30, 42, 54, 60, 72, 84, 90, 96, 108],
             [0] * 30 + [repeated_total - 1] * 30 + [17] * 40),
        case([14, 21, 28, 35, 42, 49, 56, 63],
             [unordered_total - 1, 0, 13, 1, 20, 7, 2]),
        case([49_950, 49_950, 49_975, 49_975, 50_000, 25_000],
             [0, 14, 3, 9]),
        case([30, 42, 70, 105, 210], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
    ]

    # Three explicit stress cases: large pair count, maximum V/n, and maximum Q.
    n = 100_000
    pair_count = n * (n - 1) // 2
    hidden.append(case([1] * n, [0, 2_147_483_648, pair_count - 1]))

    mixed_nums = [((index * 7_919) % 50_000) + 1 for index in range(n)]
    mixed_pairs = n * (n - 1) // 2
    hidden.append(case(
        mixed_nums,
        [((index * 1_000_003) % mixed_pairs) for index in range(257)],
    ))

    query_nums = [((index * 3571) % 50_000) + 1 for index in range(2_000)]
    query_pairs = len(query_nums) * (len(query_nums) - 1) // 2
    hidden.append(case(
        query_nums,
        [((index * 104_729) % query_pairs) for index in range(100_000)],
    ))

    if len(public) != 4 or len(hidden) != 18:
        raise AssertionError("expected 4 public and 18 hidden cases")
    write_cases(output_dir, "public_tests.json", public)
    write_cases(output_dir, "hidden_tests.json", hidden)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    generate(args.output_dir)


if __name__ == "__main__":
    main()
