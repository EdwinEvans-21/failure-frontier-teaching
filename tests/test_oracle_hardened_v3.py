from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from src.ffjudge.oracle_hardened.catalog import PROBLEMS
from src.ffjudge.oracle_hardened.generators import generate_cases
from src.ffjudge.oracle_hardened.inventory import snapshot_tree
from src.ffjudge.oracle_hardened.judge import canonical_sha256
from src.ffjudge.oracle_hardened.judge import worker_request
from src.ffjudge.models import ProblemSpec
from src.ffjudge.oracle_hardened.replay import aggregate
from src.ffjudge.oracle_hardened.policy_judge import OracleHardenedPolicyJudge
from src.ffjudge.models import Verdict


class OracleHardenedV3Tests(unittest.TestCase):
    def test_generators_are_deterministic_and_reference_agrees(self) -> None:
        for number, problem in PROBLEMS.items():
            left = generate_cases(number, random_count=8)
            right = generate_cases(number, random_count=8)
            self.assertEqual(canonical_sha256(left), canonical_sha256(right))
            for case in left:
                self.assertEqual(problem.reference(*deepcopy(case["args"])), case["expected"])

    def test_counterexample_hash_is_stable(self) -> None:
        value = {"input": {"args": [[7, 3], [3]]}, "expected": 3, "actual": -1}
        self.assertEqual(canonical_sha256(value), canonical_sha256(json.loads(json.dumps(value))))

    def test_snapshot_uses_raw_bytes_and_detects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "x.json").write_bytes(b"{\r\n}\r\n")
            before = snapshot_tree(root)
            (root / "x.json").write_bytes(b"{\n}\n")
            self.assertNotEqual(before, snapshot_tree(root))
            (root / "x.json").unlink()
            self.assertEqual({}, snapshot_tree(root))

    def test_original_verdict_is_preserved_and_v3_is_independent(self) -> None:
        row = {"original_judge_verdict": "AC"}
        replay = dict(row)
        replay["replay_judge_verdict_v3"] = "WA"
        self.assertEqual("AC", replay["original_judge_verdict"])
        self.assertEqual("WA", replay["replay_judge_verdict_v3"])

    def test_worker_request_excludes_expected_and_oracle(self) -> None:
        spec = ProblemSpec.load(Path("examples/lc-1611-minimum-one-bit-operations-to-make-integers-zero/problem.json"))
        request = worker_request(spec, [{"args": [3], "expected": 2, "oracle": {"secret": 1}}])
        rendered = json.dumps(request)
        self.assertNotIn("expected", rendered)
        self.assertNotIn("oracle", rendered)

    def test_false_ac_censoring_bounds(self) -> None:
        records = [{
            "role": "student", "problem_id": "lc-3117-x", "condition": "c",
            "root_id": "r", "lineage_repeat_index": 0, "generation": 2,
            "original_judge_verdict": "AC", "replay_judge_verdict_v3": "WA",
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        }]
        manifest = {"inventory_reconciliation": {"conditions": ["c"]}}
        out = aggregate(records, records, manifest)
        bounds = out["censoring_bounds_aggregate.json"]
        self.assertEqual([0.0, 1.0], bounds["five_generation_success_identified_interval"])
        self.assertTrue(out["false_ac_censoring.json"]["records"][0]["counterfactual_descendants_missing"])

    def test_non_frozen_file_does_not_affect_explicit_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            source.mkdir()
            (source / "a").write_text("a", encoding="utf-8")
            before = snapshot_tree(source)
            (root / "outside").write_text("changed", encoding="utf-8")
            self.assertEqual(before, snapshot_tree(source))

    def test_policy_judge_keeps_hidden_feedback_coarse(self) -> None:
        result = OracleHardenedPolicyJudge._convert(
            {"verdict": "WA", "input": {"args": ["SECRET"]},
             "expected": "SECRET_EXPECTED", "actual": "SECRET_ACTUAL",
             "runtime_ms": 3}, "hidden")
        self.assertEqual(Verdict.WRONG_ANSWER, result.verdict)
        self.assertEqual("A hidden case failed.", result.message)
        self.assertNotIn("SECRET", json.dumps(result.to_dict()))


if __name__ == "__main__":
    unittest.main()
