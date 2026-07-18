from __future__ import annotations

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "configs" / "expanded_exploratory_v1.yaml"
OUTPUT = ROOT / "experiments" / "configs" / "expanded_critical_ff_v1.yaml"


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    data["student_conditions"] = [
        "success_only",
        "failure_frontier",
        "critical_failure_frontier",
        "general_guidance",
    ]
    OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
