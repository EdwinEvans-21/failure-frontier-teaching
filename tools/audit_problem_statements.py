"""Read-only integrity audit for the five canonical model-visible statements."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.pilot.prompts import PromptRenderer  # noqa: E402
from ffjudge.models import ProblemSpec  # noqa: E402


AUDIT = Path("experiments/baseline_v2/problem_statement_audit.json")
CONFIG = Path("experiments/configs/pilot_v1.yaml")

REQUIRED_FIELDS = {
    "problem_id", "canonical_problem_json_path", "readme_path", "entrypoint",
    "public_test_path", "hidden_test_path", "oracle_path", "judge_adapter_path",
    "missing_information", "semantic_inconsistencies", "proposed_fix",
    "frozen_in_v2",
}

SEMANTIC_REQUIREMENTS = {
    "lc-0009-palindrome-number": (
        "base-10 representation", "negative integer", "minus sign", "value 0",
    ),
    "lc-3988-exact-monotone-paths": (
        "m-row by n-column", "top-left", "bottom-right", "one cell right",
        "one cell down", "using '.'", "'#'", "Return [] exactly",
    ),
    "lc-3980-minimum-operations-binary-transform": (
        "current bit is 0", "from 0 to 1", "two adjacent positions",
        "current bits are both 1", "from 11 to 00", "costs one operation",
        "applied repeatedly", "never 00 to 11", "unreachable",
    ),
    "lc-3312-sorted-gcd-pair-queries": (
        "i < j", "unordered pair of distinct positions", "repeated GCD values",
        "nondecreasing order", "zero-indexed", "original order of queries",
    ),
    "lc-3962-maximum-subarray-sum-after-k-swaps": (
        "at most k", "two distinct array indices", "need not be adjacent",
        "more than one operation", "fewer than k swaps", "including zero swaps",
        "non-empty contiguous subarray",
    ),
}


def audit(root: Path) -> list[str]:
    root = root.resolve()
    records = json.loads((root / AUDIT).read_text(encoding="utf-8"))["records"]
    config = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    configured = {item["problem"] for item in config["problems"]}
    renderer = PromptRenderer(root / "experiments/prompts")
    errors: list[str] = []
    if len(records) != 5:
        errors.append("audit must contain exactly five problem records")
    for record in records:
        missing_fields = REQUIRED_FIELDS - set(record)
        if missing_fields:
            errors.append(f"audit record missing required fields: {record.get('problem_id', 'unknown')}")
            continue
        problem_path = root / record["canonical_problem_json_path"]
        public_path = root / record["public_test_path"]
        paths = [
            problem_path, public_path, root / record["hidden_test_path"],
            root / record["readme_path"],
            *(root / path for path in record["judge_adapter_path"]),
        ]
        if record["oracle_path"]:
            paths.append(root / record["oracle_path"])
        if any(not path.is_file() for path in paths):
            errors.append(f"audit path missing: {record['problem_id']}")
            continue
        if record["canonical_problem_json_path"] not in configured:
            errors.append(f"canonical problem is not configured: {record['problem_id']}")
        spec = ProblemSpec.load(problem_path)
        if spec.problem_id != record["problem_id"]:
            errors.append(f"problem_id mismatch: {record['problem_id']}")
        rendered = renderer.formatted_problem(problem_path, public_path)
        for value in (spec.title, spec.description, spec.input_contract,
                      spec.output_contract, spec.entrypoint.method or ""):
            if value not in rendered:
                errors.append(f"rendered prompt omitted canonical field: {record['problem_id']}")
        for phrase in SEMANTIC_REQUIREMENTS.get(record["problem_id"], ()):
            if phrase not in rendered:
                errors.append(f"rendered prompt missing required semantics: {record['problem_id']}")
        public_count = len(json.loads(public_path.read_text(encoding="utf-8")))
        if rendered.count("Example ") != public_count:
            errors.append(f"public example count mismatch: {record['problem_id']}")
        if record["missing_information"] or record["semantic_inconsistencies"]:
            errors.append(f"unresolved statement finding: {record['problem_id']}")
        if record["frozen_in_v2"] is not True:
            errors.append(f"problem is not marked frozen in v2: {record['problem_id']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        errors = audit(args.root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Problem statement audit could not run: {type(error).__name__}", file=sys.stderr)
        return 2
    if errors:
        print(f"Problem statement audit failed with {len(errors)} issue(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Five-problem statement audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
