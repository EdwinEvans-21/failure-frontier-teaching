"""Regenerate deterministic formal tests for the LC 3980 experiment fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ffjudge.oracles.minimum_operations_binary_transform import (
    min_operations_reference,
)


ROOT = Path(__file__).parents[1] / "examples" / "minimum_operations_binary_transform"


def case(s1: str, s2: str) -> dict[str, object]:
    return {
        "args": [s1, s2],
        "expected": min_operations_reference(s1, s2),
    }


def write_cases(
    output_dir: Path, filename: str, pairs: list[tuple[str, str]]
) -> None:
    payload = [case(s1, s2) for s1, s2 in pairs]
    (output_dir / filename).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    public_pairs = [
        ("00", "11"),
        ("11", "00"),
        ("10", "01"),
        ("101", "101"),
    ]

    hidden_pairs = [
        # All four length-one transformations.
        ("0", "0"),
        ("0", "1"),
        ("1", "0"),
        ("1", "1"),
        # Identity, uniform, and alternating families.
        ("0101010101010101", "0101010101010101"),
        ("0" * 32, "1" * 32),
        ("1" * 32, "0" * 32),
        ("01" * 8, "10" * 8),
        ("10" * 8, "01" * 8),
        # Creation-before-pairing and overlapping adjacent operations.
        ("10", "00"),
        ("010", "000"),
        ("111", "000"),
        ("1111", "0000"),
        ("10101", "00000"),
        # Greedy traps and both string boundaries.
        ("11011", "00000"),
        ("10110", "00001"),
        ("100000", "000000"),
        ("000001", "000000"),
        ("100001", "000000"),
        # Mixed reachable cases.
        ("00101101", "11000010"),
        ("1110100110", "0011011001"),
        # Linear-time stress cases.
        ("01" * 50_000, "10" * 50_000),
        ("1" * 100_000, "0" * 100_000),
        ("00110101" * 12_500, "00110101" * 12_500),
    ]

    if len(hidden_pairs) != 24:
        raise AssertionError("the formal hidden suite must contain 24 cases")
    write_cases(output_dir, "public_tests.json", public_pairs)
    write_cases(output_dir, "hidden_tests.json", hidden_pairs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    generate(args.output_dir)


if __name__ == "__main__":
    main()
