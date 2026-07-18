from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.expanded_benchmark_catalog import records


OUTPUT = ROOT / "experiments" / "configs" / "expanded_exploratory_v1.yaml"


def main() -> int:
    config = json.loads(
        (ROOT / "experiments" / "configs" / "pilot_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    config["baseline_id"] = "failure-frontier-baseline-v3-expanded"
    config["baseline_manifest"] = (
        "experiments/baseline_v3_expanded/baseline_manifest.json"
    )
    config["execution"]["output_root"] = "experiments/runs-expanded"
    config["problems"] = [
        {
            "problem": f"examples/{item['problem_id']}/problem.json",
            "public_tests": f"examples/{item['problem_id']}/public_tests.json",
            "hidden_tests": f"examples/{item['problem_id']}/hidden_tests.json",
        }
        for item in records()
    ]
    OUTPUT.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} with {len(config['problems'])} problems.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
