from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from experiments.pilot.eligibility import (
    ELIGIBILITY_POLICY,
    analyze_historical_eligibility,
    derive_comparison_eligibility,
    finalize_comparison_eligibility,
)
from experiments.pilot.orchestrator import build_summary


def completed_student(verdict: str = "WA") -> dict:
    return {
        "verdict": verdict,
        "planning_calls": 1,
        "final_calls": 1,
        "judge_submissions": 1,
    }


def failure_record(*, matched: bool = True, fallback: bool = False) -> dict:
    return {
        "problem_id": "failure",
        "branch": "teacher_failure",
        "teacher": {"verdict": "WA", "truncated": False},
        "valid_episode": True,
        "infrastructure_error": None,
        "teaching_material": {
            "type": "failure",
            "failure_frontier_tokens": 1000,
            "failure_frontier_truncated": False,
            "token_match_passed": matched,
            "token_match_failed": not matched,
            "fallback_used": fallback,
            "selected_version": 0,
            "selected_within_token_interval": matched,
            "token_interval_outcome": (
                "matched_within_tolerance"
                if matched
                else "fallback_outside_tolerance"
            ),
            "general_guidance_tokens": 1000,
            "general_guidance_truncated": False,
            "semantic_completeness_passed": True,
            "forbidden_content": [],
            "obviously_truncated": False,
        },
        "students": {
            "success_only": completed_student(),
            "failure_frontier": completed_student(),
            "general_guidance": completed_student(),
        },
    }


def success_record(problem_id: str = "success") -> dict:
    return {
        "problem_id": problem_id,
        "branch": "teacher_success",
        "teacher": {"verdict": "AC", "truncated": False},
        "valid_episode": True,
        "teaching_material": {"type": "success"},
        "students": {
            "success_only": completed_student("AC"),
            "failure_frontier": completed_student("AC"),
            "general_guidance": completed_student("AC"),
        },
    }


class EligibilityDerivationTests(unittest.TestCase):
    def test_teacher_success_is_never_strictly_eligible(self) -> None:
        result = derive_comparison_eligibility(success_record())
        self.assertFalse(result.condition_comparison_eligible)
        self.assertFalse(result.exploratory_comparison_eligible)
        self.assertEqual(result.eligibility_reason, "teacher_success_branch")

    def test_teacher_failure_strict_match_is_eligible(self) -> None:
        result = derive_comparison_eligibility(failure_record())
        self.assertTrue(result.condition_comparison_eligible)
        self.assertEqual(result.eligibility_reason, "eligible")
        self.assertEqual(result.eligibility_policy, ELIGIBILITY_POLICY)

    def test_failure_frontier_at_output_limit_is_never_comparable(self) -> None:
        record = failure_record()
        material = record["teaching_material"]
        material["failure_frontier_tokens"] = 8192
        material["failure_frontier_max_output_tokens"] = 8192
        material["failure_frontier_output_limit_reached"] = True
        result = derive_comparison_eligibility(record)
        self.assertFalse(result.condition_comparison_eligible)
        self.assertFalse(result.exploratory_comparison_eligible)
        self.assertEqual(
            result.eligibility_reason,
            "failure_frontier_output_limit_reached",
        )

    def test_inconsistent_token_match_metadata_is_ineligible(self) -> None:
        record = failure_record()
        record["teaching_material"]["selected_within_token_interval"] = False
        result = derive_comparison_eligibility(record)
        self.assertFalse(result.condition_comparison_eligible)
        self.assertIn("gg_token_outside_interval", result.eligibility_reasons)

    def test_fallback_is_exploratory_but_not_strict(self) -> None:
        result = derive_comparison_eligibility(
            failure_record(matched=False, fallback=True)
        )
        self.assertFalse(result.condition_comparison_eligible)
        self.assertTrue(result.exploratory_comparison_eligible)
        self.assertEqual(result.eligibility_reason, "gg_token_outside_interval")

    def test_truncated_fallback_is_exploratory_not_formal(self) -> None:
        record = failure_record(matched=False, fallback=True)
        record["teaching_material"]["general_guidance_truncated"] = True
        record["teaching_material"]["semantic_completeness_passed"] = False
        result = derive_comparison_eligibility(record)
        self.assertFalse(result.condition_comparison_eligible)
        self.assertTrue(result.exploratory_comparison_eligible)
        self.assertIn("gg_candidate_truncated", result.eligibility_reasons)

    def test_format_invalid_fallback_inside_interval_is_formal(self) -> None:
        record = failure_record(matched=False, fallback=True)
        material = record["teaching_material"]
        material["selected_within_token_interval"] = True
        material["token_interval_outcome"] = (
            "fallback_within_tolerance_format_exception"
        )
        material["semantic_completeness_passed"] = False
        result = derive_comparison_eligibility(record)
        self.assertTrue(result.condition_comparison_eligible)
        self.assertFalse(result.exploratory_comparison_eligible)
        self.assertEqual(result.eligibility_reason, "eligible")

    def test_incomplete_student_is_ineligible(self) -> None:
        record = failure_record()
        del record["students"]["general_guidance"]
        result = derive_comparison_eligibility(record)
        self.assertFalse(result.condition_comparison_eligible)
        self.assertIn("students_incomplete", result.eligibility_reasons)

    def test_infrastructure_error_has_deterministic_primary_reason(self) -> None:
        record = failure_record()
        record["valid_episode"] = False
        record["infrastructure_error"] = "judge"
        result = derive_comparison_eligibility(record)
        self.assertFalse(result.condition_comparison_eligible)
        self.assertEqual(result.eligibility_reason, "infrastructure_error")
        self.assertEqual(
            result.eligibility_reasons[:2],
            ("infrastructure_error", "invalid_episode"),
        )

    def test_finalization_writes_canonical_fields(self) -> None:
        record = failure_record()
        record["condition_comparison_eligible"] = False
        finalize_comparison_eligibility(record)
        self.assertTrue(record["condition_comparison_eligible"])
        self.assertFalse(record["exploratory_comparison_eligible"])
        self.assertEqual(record["eligibility_reason"], "eligible")
        self.assertEqual(record["eligibility_policy"], ELIGIBILITY_POLICY)

    def test_historical_success_record_is_analyzed_without_mutation(self) -> None:
        record = success_record("legacy-success")
        record.pop("branch")
        record["condition_comparison_eligible"] = True
        original = deepcopy(record)
        analysis = analyze_historical_eligibility(record)
        self.assertTrue(
            analysis["runner_reported_condition_comparison_eligible"]
        )
        self.assertFalse(
            analysis["protocol_condition_comparison_eligible"]
        )
        self.assertIn(
            "legacy_condition_comparison_eligibility_drift",
            analysis["compatibility_warnings"],
        )
        self.assertEqual(record, original)

    def test_historical_analysis_cli_preserves_source_bytes(self) -> None:
        record = success_record("legacy-success")
        record.pop("branch")
        record["condition_comparison_eligible"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/analyze_pilot_eligibility.py",
                    "--record",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            analysis = json.loads(completed.stdout)["records"][0]
            self.assertTrue(
                analysis["runner_reported_condition_comparison_eligible"]
            )
            self.assertFalse(
                analysis["protocol_condition_comparison_eligible"]
            )
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_formal_run_summary_regression_has_zero_strict_denominator(self) -> None:
        records = [success_record(f"success-{index}") for index in range(3)]
        for index in range(2):
            record = failure_record(matched=False, fallback=True)
            record["problem_id"] = f"failure-{index}"
            records.append(record)
        summary = build_summary("formal-regression", records)
        self.assertEqual(summary["total_valid_episodes"], 5)
        self.assertEqual(summary["teacher_success_episodes"], 3)
        self.assertEqual(summary["teacher_failure_episodes"], 2)
        self.assertEqual(
            summary["strict_condition_comparison_eligible_episodes"], 0
        )
        self.assertEqual(summary["condition_comparison_eligible_count"], 0)
        self.assertEqual(summary["ineligible_teacher_failure_episodes"], 2)
        self.assertEqual(summary["fallback_exploratory_episodes"], 2)
        self.assertEqual(summary["teacher_ac_count"], 3)
        self.assertEqual(summary["teacher_failure_count"], 2)


if __name__ == "__main__":
    unittest.main()
