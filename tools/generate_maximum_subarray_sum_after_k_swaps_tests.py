"""Regenerate deterministic formal tests for the LC 3962 fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random

from ffjudge.oracles.maximum_subarray_sum_after_k_swaps import max_sum_reference


ROOT = Path(__file__).parents[1] / "examples" / "maximum_subarray_sum_after_k_swaps"


def case(nums: list[int], k: int) -> dict[str, object]:
    return {"args": [nums, k], "expected": max_sum_reference(nums, k)}


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
        case([1, -1, 0, 2], 1),
        case([4, 3, 2, 4], 2),
        case([-1, -2], 0),
        case([3, -5, 4, -1, 2], 1),
    ]

    hidden = [
        case([7], 0),
        case([-100_000], 1),
        case([4, -1, 2, 1, -7, 5], 0),
        case([-3, 8, -2, 7, -9], 5),
        case([1, 2, 3, 4, 5], 3),
        case([-8, -3, -11, -4], 2),
        case([0, 0, 0, 0, 0], 4),
        case([9, -10, 8, -10, 7, -10, 6], 2),
        case([5] * 30 + [-5] * 40 + [5] * 30, 15),
        case([-100, 50, -100], 0),
        case([3, 4, 5, 6], 1),
        case([8, 2, -20, -30], 1),
        case([-30, -20, 2, 8], 1),
        case([10, -100, 1, 1], 1),
        case([1, 1, -100, 10], 1),
        case([9, -100, -100, 8], 1),
        case([-1, -2, -3, -4, 6, -6, -7, 7, -9, -10, 7], 1),
        case([5, -10, 4, -10, 3, -10, 2], 2),
        case([-5, 2, -5, 2], 2),
        case([100, -20, -20, -20, -20, -20, 3, 3], 1),
        case([9, -100, 4, 5, -100, 9], 1),
        case([100_000, -100_000, 100_000, -100_000], 1),
    ]

    rng = Random(3962)
    random_nums = [rng.randint(-100_000, 100_000) for _ in range(1_500)]
    alternating = [
        100_000 if index % 2 == 0 else -100_000
        for index in range(1_500)
    ]
    repeated = [7] * 500 + [-3] * 500 + [7] * 500
    triples = [100_000, 100_000, -100_000] * 500

    # Seven explicit n=1500 pressure cases spanning the required k/patterns.
    hidden.extend([
        case(random_nums, 0),
        case(random_nums, 1),
        case(random_nums, 750),
        case(random_nums, 1_500),
        case(alternating, 750),
        case(repeated, 500),
        case(triples, 200),
    ])

    if len(public) != 4 or len(hidden) != 29:
        raise AssertionError("expected 4 public and 29 hidden cases")
    write_cases(output_dir, "public_tests.json", public)
    write_cases(output_dir, "hidden_tests.json", hidden)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    generate(args.output_dir)


if __name__ == "__main__":
    main()
