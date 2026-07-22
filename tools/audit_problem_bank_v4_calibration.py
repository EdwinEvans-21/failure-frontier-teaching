from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ffjudge.models import ProblemSpec
from src.ffjudge.oracles.problem_bank_v4_calibration import (
    critical_edges_oracle,
    critical_edges_reference,
    count_routes_oracle,
    count_routes_reference,
    minimum_days_oracle,
    minimum_days_reference,
    maximum_requests_oracle,
    maximum_requests_reference,
    remove_edges_oracle,
    remove_edges_reference,
    parallel_courses_oracle,
    parallel_courses_reference,
    stone_game_v_oracle,
    stone_game_v_reference,
    strange_printer_ii_oracle,
    strange_printer_ii_reference,
    string_compression_oracle,
    string_compression_reference,
)
from src.ffjudge.oracles.expanded_dp import minimum_cut_cost_bruteforce, minimum_cut_cost_reference
from tools.generate_problem_bank_v4_calibration import CALIBRATION, SEED, connected_graph


def invoke(path: Path, spec: ProblemSpec, args: list[Any]) -> Any:
    namespace: dict[str, Any] = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    instance = namespace[spec.entrypoint.class_name]()
    return getattr(instance, spec.entrypoint.method)(*args)


def passed(spec: ProblemSpec, case: dict[str, Any], actual: Any) -> bool:
    return actual == case["expected"]


def differential(number: int) -> tuple[int, float]:
    target = 10_000
    started = time.perf_counter()
    done = 0
    for seed_index in range(10):
        rng = random.Random(SEED + number * 100 + seed_index)
        share = target // 10
        for index in range(share):
            if number == 1489:
                n = rng.randint(2, 6)
                edges = connected_graph(rng, n, rng.randint(0, min(4, n * (n - 1) // 2 - n + 1)))
                args = [n, edges]
                fast, slow = critical_edges_reference(*args), critical_edges_oracle(*args)
                fast, slow = [sorted(x) for x in fast], [sorted(x) for x in slow]
            elif number == 1494:
                n = rng.randint(1, 6)
                relations = []
                for course in range(2, n + 1):
                    for prev in range(1, course):
                        if rng.random() < 0.3:
                            relations.append([prev, course])
                args = [n, relations, rng.randint(1, max(1, n))]
                fast, slow = parallel_courses_reference(*args), parallel_courses_oracle(*args)
            elif number == 1531:
                length = rng.randint(1, 8)
                s = "".join(rng.choice("abcde") for _ in range(length))
                args = [s, rng.randint(0, min(4, length))]
                fast, slow = string_compression_reference(*args), string_compression_oracle(*args)
            elif number == 1547:
                n = rng.randint(2, 12)
                cuts = sorted(rng.sample(range(1, n), rng.randint(1, min(5, n - 1))))
                args = [n, cuts]
                fast, slow = minimum_cut_cost_reference(*args), minimum_cut_cost_bruteforce(*args)
            elif number == 1553:
                args = [rng.randint(1, 1000)]
                fast, slow = minimum_days_reference(*args), minimum_days_oracle(*args)
            elif number == 1563:
                length = rng.randint(2, 8)
                args = [[rng.randint(1, 10) for _ in range(length)]]
                fast, slow = stone_game_v_reference(args[0]), stone_game_v_oracle(args[0])
            elif number == 1575:
                length = rng.randint(2, 6)
                locations = sorted(rng.sample(range(0, 20), length))
                args = [locations, rng.randrange(length), rng.randrange(length), rng.randint(0, 12)]
                fast, slow = count_routes_reference(*args), count_routes_oracle(*args)
            elif number == 1579:
                n = rng.randint(2, 5)
                edges = []
                for _ in range(rng.randint(n, n + 4)):
                    edge_type = rng.randint(1, 3)
                    u, v = rng.sample(range(1, n + 1), 2)
                    edges.append([edge_type, u, v])
                args = [n, edges]
                fast, slow = remove_edges_reference(*args), remove_edges_oracle(*args)
            elif number == 1591:
                rows = rng.randint(1, 4)
                cols = rng.randint(1, 4)
                grid = [[rng.randint(1, 3) for _ in range(cols)] for _ in range(rows)]
                args = [grid]
                fast, slow = strange_printer_ii_reference(*args), strange_printer_ii_oracle(*args)
            elif number == 1601:
                n = rng.randint(2, 5)
                requests = []
                for _ in range(rng.randint(n, n + 4)):
                    u, v = rng.sample(range(n), 2)
                    requests.append([u, v])
                args = [n, requests]
                fast, slow = maximum_requests_reference(*args), maximum_requests_oracle(*args)
            else:
                raise AssertionError(number)
            if fast != slow:
                raise AssertionError(f"differential mismatch for {number}: {args!r}")
            done += 1
    return done, time.perf_counter() - started


def audit(output: Path) -> dict[str, Any]:
    rows = []
    for number in CALIBRATION:
        directory = next((ROOT / "examples").glob(f"lc-{number}-*"))
        spec = ProblemSpec.load(directory / "problem.json")
        public = json.loads((directory / "public_tests.json").read_text(encoding="utf-8"))
        hidden = json.loads((directory / "hidden_tests.json").read_text(encoding="utf-8"))
        stress = json.loads((directory / "stress_tests.json").read_text(encoding="utf-8"))
        for case in public + hidden:
            assert passed(spec, case, invoke(directory / "accepted.py", spec, case["args"]))
        differential_count, differential_runtime = differential(number)
        mutant_results = {}
        for mutant in sorted(directory.glob("wrong_semantic_*.py")):
            killed = False
            for case in public + hidden:
                try:
                    killed = not passed(spec, case, invoke(mutant, spec, case["args"]))
                except Exception:
                    killed = True
                if killed:
                    break
            mutant_results[mutant.name] = killed
        stress_started = time.perf_counter()
        for case in stress:
            assert passed(spec, case, invoke(directory / "accepted.py", spec, case["args"]))
        stress_runtime = time.perf_counter() - stress_started
        score = sum(mutant_results.values()) / len(mutant_results)
        assert len(public) >= 5 and len(hidden) >= 60 and len(stress) >= 3
        assert score >= 0.9
        rows.append({
            "problem_id": spec.problem_id,
            "public_test_count": len(public),
            "hidden_test_count": len(hidden),
            "stress_case_count": len(stress),
            "differential_case_count": differential_count,
            "differential_runtime_seconds": round(differential_runtime, 6),
            "reference_oracle_mismatches": 0,
            "mutation_count": len(mutant_results),
            "mutation_score": score,
            "mutants": mutant_results,
            "stress_runtime_seconds": round(stress_runtime, 6),
            "quality_gate_status": "PASSED",
        })
    report = {
        "schema_version": "1.0",
        "generator_seed": SEED,
        "calibration_problem_count": len(rows),
        "problems": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/problem_bank_v4_100/calibration_quality.json")
    args = parser.parse_args()
    report = audit(args.output)
    print(json.dumps({"problems": report["calibration_problem_count"], "status": "PASSED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
