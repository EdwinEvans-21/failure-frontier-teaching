"""Run bounded, independent differential audits for hardened LC69 fixtures.

This offline tool never participates in a student judge invocation.  It writes
only aggregate diagnostics unless a mismatch occurs; the latter is fail-closed
and records the first minimized reproducible input in the local audit artifact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any, Callable
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ffjudge.oracles.lc69_independent import ORACLES, ORACLE_METADATA

SEEDS = (20260721, 20260722, 20260723, 20260724, 20260725,
         20260726, 20260727, 20260728, 20260729, 20260730)


def _strings(rng: random.Random) -> list[Any]:
    length_a = rng.choice((1, 2, rng.randint(3, 10), rng.randint(8, 12)))
    length_b = rng.choice((1, 2, rng.randint(3, 10), rng.randint(8, 12)))
    alphabet = rng.choice(("a", "ab", "abc", "abcd"))
    return ["".join(rng.choice(alphabet) for _ in range(length_a)),
            "".join(rng.choice(alphabet) for _ in range(length_b))]


def _dice(rng: random.Random) -> list[Any]:
    dice = rng.choice((1, 2, 3, 4, 5))
    faces = rng.choice((2, 3, 4, 5))
    target = rng.choice((1, dice, dice * faces, dice * faces + 1,
                         rng.randint(1, dice * faces)))
    return [dice, faces, target]


GENERATORS: dict[int, Callable[[random.Random], list[Any]]] = {
    1143: _strings,
    1155: _dice,
}


def _solution(number: int):
    fixture = next((ROOT / "examples").glob(f"lc-{number:04d}-*"))
    problem = json.loads((fixture / "problem.json").read_text(encoding="utf-8"))
    namespace = {"__name__": "lc69_reference_" + hashlib.sha256(str(fixture).encode()).hexdigest()}
    source = fixture / "accepted.py"
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
    return getattr(namespace["Solution"](), problem["entrypoint"]["method"])


def audit(number: int, per_seed: int) -> dict[str, Any]:
    if number not in GENERATORS:
        raise ValueError(f"bounded generator not implemented for lc-{number}")
    reference = _solution(number)
    oracle = ORACLES[number]
    started = time.perf_counter()
    valid_count = 0
    reference_failures = 0
    oracle_failures = 0
    mismatches = 0
    first_mismatch: dict[str, Any] | None = None
    for seed in SEEDS:
        rng = random.Random(seed * 10000 + number)
        for _ in range(per_seed):
            args = GENERATORS[number](rng)
            try:
                expected = reference(*copy.deepcopy(args))
            except Exception:
                reference_failures += 1
                continue
            try:
                actual = oracle(*copy.deepcopy(args))
            except Exception:
                oracle_failures += 1
                continue
            valid_count += 1
            if actual != expected:
                mismatches += 1
                if first_mismatch is None:
                    first_mismatch = {"seed": seed, "args": args,
                                      "reference": expected, "oracle": actual}
    return {
        "problem_number": number,
        "oracle_metadata": ORACLE_METADATA[number],
        "generated_count": per_seed * len(SEEDS),
        "valid_count": valid_count,
        "seed": list(SEEDS),
        "reference_failures": reference_failures,
        "oracle_failures": oracle_failures,
        "mismatches": mismatches,
        "first_mismatch": first_mismatch,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "passed": reference_failures == oracle_failures == mismatches == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", type=int, required=True)
    parser.add_argument("--per-seed", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = audit(arguments.problem, arguments.per_seed)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("problem_number", "generated_count", "valid_count", "mismatches", "passed", "runtime_seconds")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
