from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.expanded_benchmark_catalog import records


def _solution(path: Path):
    namespace = {"__name__": "bench_" + hashlib.sha256(str(path).encode()).hexdigest()}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace["Solution"]()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    for record in records():
        fixture = ROOT / "examples" / str(record["problem_id"])
        cases = json.loads((fixture / "stress_tests.json").read_text(encoding="utf-8"))
        method = getattr(_solution(fixture / "accepted.py"), str(record["method"]))
        variants = []
        all_samples = []
        for case_index, case in enumerate(cases):
            samples = []
            for _ in range(args.repetitions):
                started = time.perf_counter()
                actual = method(*copy.deepcopy(case["args"]))
                elapsed = (time.perf_counter() - started) * 1000
                if actual != case["expected"]:
                    raise RuntimeError(f"reference drift for {record['problem_id']}")
                samples.append(round(elapsed, 3))
                all_samples.append(elapsed)
            variants.append({"case_index": case_index, "samples_ms": samples,
                             "median_ms": round(statistics.median(samples), 3)})
        results.append({
            "problem_id": record["problem_id"],
            "stress_input_bytes": (fixture / "stress_tests.json").stat().st_size,
            "stress_case_count": len(cases),
            "variants": variants,
            "median_ms": round(statistics.median(all_samples), 3),
            "maximum_ms": round(max(all_samples), 3),
        })
        print(f"{record['problem_id']}: max={max(all_samples):.3f} ms")
    payload = {
        "clock": "time.perf_counter",
        "scope": "Solution method only; JSON parsing and process/container startup excluded",
        "repetitions": args.repetitions,
        "results": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
