from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest

from ffjudge.models import JudgeResult, Verdict

from experiments.pilot.config import load_config
from experiments.pilot.model_client import MockModelClient, ModelInfrastructureError
from experiments.pilot.orchestrator import (
    GGContentValidationError,
    PilotRunner,
    guidance_distance_to_interval,
    guidance_token_bounds,
    validate_guidance_content,
)


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "experiments/configs/pilot_v1.yaml"
PROBLEM_ID = "lc-0009-palindrome-number"
FORMATTED_PROBLEM = "PUBLIC PROBLEM STATEMENT"


def solver(marker: str) -> str:
    return (
        "## Approach\nMock solver.\n\n## Code\n```python\n"
        f"# {marker}\nclass Solution:\n    pass\n```"
    )


def guidance(marker: str) -> str:
    return (
        "## Constraint Analysis\nThe input size constraints require O(n) time "
        "complexity and bounded space complexity.\n\n"
        "## Plausible Approaches\nCompare a greedy algorithm with dynamic "
        "programming before selecting an approach.\n\n"
        "## Edge Cases\nCheck edge cases and boundaries; use an invariant "
        "to justify correctness.\n\n"
        "## Implementation Checks\nCheck implementation risks such as indexing, "
        f"overflow, and data types. {marker}."
    )


def alias_guidance(marker: str = "ALIAS") -> str:
    return (
        "## Constraints and Observations\nInput size constraints require O(n) time "
        "complexity and bounded space complexity.\n\n"
        "## Possible Algorithms\nCompare a greedy algorithm with dynamic "
        "programming before selecting an approach.\n\n"
        "## Correctness, Pitfalls, and Edge Cases\nUse an invariant for "
        "correctness and check edge cases and boundaries.\n\n"
        "## Implementation Notes\nImplementation risks include indexing, "
        f"overflow, and data types. {marker}."
    )


def unheaded_guidance() -> str:
    return (
        "1. The input size constraints require O(n) time complexity and bounded "
        "space complexity for the upper bound.\n\n"
        "2. Compare a greedy algorithm and dynamic programming as candidate "
        "approaches before choosing the more suitable algorithm.\n\n"
        "3. Prove correctness with an invariant and examine edge cases, "
        "boundaries, and impossible inputs.\n\n"
        "4. Implementation checks should cover indexing, overflow, data types, "
        "and other coding risks."
    )


def item(content: str, tokens: int | None, *, finish_reason: str = "stop") -> dict:
    total = 50 + tokens if tokens is not None else 50
    return {
        "content": content,
        "input_tokens": 50,
        "output_tokens": tokens,
        "total_tokens": total,
        "finish_reason": finish_reason,
    }


class NoJudge:
    def judge(self, *args, **kwargs):
        raise AssertionError("judge must not be called by direct GG tests")


class MarkerJudge:
    def __init__(self) -> None:
        self.calls = 0

    def judge(self, submission, problem, tests, *, phase):
        self.calls += 1
        source = Path(submission).read_text(encoding="utf-8")
        verdict = Verdict.ACCEPTED if "AC_MARKER" in source else Verdict.WRONG_ANSWER
        return JudgeResult(verdict, phase, 0, 1, 1, "")


class GeneralGuidanceTokenControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def config(self, responses: dict[str, list[dict]], *, attempts: int = 2):
        script = self.root / "responses.json"
        script.write_text(json.dumps(responses), encoding="utf-8")
        base = load_config(CONFIG)
        return replace(
            base,
            problems=(base.problems[0],),
            model=replace(base.model, mock_responses_path=str(script)),
            teaching_material=replace(
                base.teaching_material, max_regeneration_attempts=attempts
            ),
            execution=replace(base.execution, output_root=str(self.root / "runs")),
            prompts_dir=str(ROOT / "experiments/prompts"),
            baseline_manifest=str(
                ROOT / "experiments/baseline_v2/baseline_manifest.json"
            ),
        )

    def direct(self, responses: dict[str, list[dict]], *, target: int,
               attempts: int = 2):
        config = self.config(responses, attempts=attempts)
        model = MockModelClient(config.model)
        runner = PilotRunner(
            config, model, judge=NoJudge(), project_root=ROOT
        )
        result = runner._matched_guidance(
            self.root / "problem", PROBLEM_ID, FORMATTED_PROBLEM, target
        )
        match = json.loads(
            (self.root / "problem/teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        return result, match, model, runner

    def test_interval_uses_ceil_and_floor(self) -> None:
        self.assertEqual(guidance_token_bounds(1168, 0.10), (1052, 1284))
        self.assertEqual(guidance_distance_to_interval(1051, 1052, 1284), 1)
        self.assertEqual(guidance_distance_to_interval(1168, 1052, 1284), 0)
        self.assertEqual(guidance_distance_to_interval(1285, 1052, 1284), 1)

    def test_initial_version_matches_and_stops(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("INITIAL MATCH"), 980)
            ],
        }, target=1000)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 0)
        self.assertEqual(match["selected_version"], 0)
        self.assertEqual(match["attempts_used"], 1)
        self.assertEqual(len(model.calls), 1)
        version = match["versions"][0]
        self.assertTrue(version["preferred_structure"])
        self.assertTrue(version["semantic_completeness_passed"])
        self.assertTrue(version["valid_candidate"])
        self.assertEqual(match["selected_validation"]["missing_categories"], [])

    def test_too_long_compresses_with_ratios_and_dynamic_limit(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("COMPRESSED MATCH"), 1030)
            ],
        }, target=1000)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(match["dynamic_max_tokens"], 1164)
        self.assertEqual([call["max_output_tokens"] for call in model.calls],
                         [1164, 1164])
        prompt = model.calls[1]["system_prompt"]
        self.assertIn("33.3%", prompt)
        self.assertIn("66.7%", prompt)

    def test_too_short_expands_and_stops_on_success(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("SHORT"), 600)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_1"): [
                item(guidance("EXPANDED MATCH"), 1010)
            ],
        }, target=1000)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(len(model.calls), 2)
        self.assertIn("66.7% longer", model.calls[1]["system_prompt"])

    def test_intermediate_match_prevents_oscillation_call(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("MATCH"), 1000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_2"): [
                item(guidance("MUST NOT BE USED"), 2800)
            ],
        }, target=1000)
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(match["attempts_used"], 2)
        self.assertEqual(len(model.calls), 2)

    def test_all_failed_oscillation_selects_closest_not_last(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("V0"), 3026)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("V1 BEST"), 698)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_2"): [
                item(guidance("V2"), 2884)
            ],
        }, target=1110)
        self.assertFalse(result["metrics"]["token_match_passed"])
        self.assertTrue(result["metrics"]["token_match_failed"])
        self.assertEqual(result["response"].output_tokens, 698)
        self.assertEqual(match["selected_version"], 1)
        self.assertEqual(match["selection_reason"],
                         "closest_valid_candidate_for_audit")
        self.assertEqual([v["completion_tokens"] for v in match["versions"]],
                         [3026, 698, 2884])
        self.assertEqual(len(model.calls), 3)
        self.assertIn("36.7%", model.calls[1]["system_prompt"])
        self.assertIn("63.3%", model.calls[1]["system_prompt"])
        self.assertIn("59.0% longer", model.calls[2]["system_prompt"])

    def test_finish_reason_length_inside_interval_is_never_matched(self) -> None:
        key = MockModelClient.key
        config = self.config({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("TRUNCATED"), 1110, finish_reason="length")
            ],
        }, attempts=0)
        model = MockModelClient(config.model)
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        with self.assertRaisesRegex(GGContentValidationError, "no semantically"):
            runner._matched_guidance(
                self.root / "problem", PROBLEM_ID, FORMATTED_PROBLEM, 1110
            )
        match = json.loads(
            (self.root / "problem/teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(match["token_match_passed"])
        self.assertIsNone(match["selected_version"])
        self.assertEqual(match["versions"][0]["status"],
                         "INVALID_FINISH_REASON")
        self.assertFalse(match["versions"][0]["valid_candidate"])

    def test_length_finish_can_use_one_remaining_adjustment(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("TRUNCATED"), 1000, finish_reason="length")
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("COMPLETE"), 1000)
            ],
        }, target=1000, attempts=1)
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(len(model.calls), 2)

    def test_missing_completion_usage_stops_without_estimation(self) -> None:
        key = MockModelClient.key
        config = self.config({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("NO USAGE"), None)
            ],
        })
        model = MockModelClient(config.model)
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        with self.assertRaisesRegex(ModelInfrastructureError, "API usage validation"):
            runner._matched_guidance(
                self.root / "problem", PROBLEM_ID, FORMATTED_PROBLEM, 1000
            )
        self.assertEqual(len(model.calls), 1)
        self.assertFalse(list(self.root.rglob("content.md")))

    def test_prompts_are_isolated_from_teacher_ff_and_verdict(self) -> None:
        key = MockModelClient.key
        _, _, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("MATCH"), 1000)
            ],
        }, target=1000)
        forbidden = (
            "TEACHER_RESPONSE_SENTINEL", "TEACHER_CODE_SENTINEL",
            "VERDICT_SENTINEL", "FF_MATERIAL_SENTINEL",
            "HIDDEN_TEST_SENTINEL", "JUDGE_SENTINEL",
        )
        for call in model.calls:
            visible = call["system_prompt"] + "\n" + call["user_prompt"]
            self.assertFalse(any(value in visible for value in forbidden))
            self.assertIn(FORMATTED_PROBLEM, call["user_prompt"])

    def test_total_calls_never_exceed_initial_plus_adjustments(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("V0"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("V1"), 600)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_2"): [
                item(guidance("V2"), 2800)
            ],
        }, target=1000, attempts=2)
        self.assertEqual(len(model.calls), 3)
        self.assertEqual(match["attempts_used"], 3)

    def test_resume_reuses_saved_versions_and_same_selection(self) -> None:
        key = MockModelClient.key
        responses = {
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("MATCH"), 1030)
            ],
        }
        config = self.config(responses)
        model = MockModelClient(config.model)
        problem_dir = self.root / "problem"
        version0 = problem_dir / "teaching_materials/general_guidance/version_0"
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        rendered = runner._rendered_call(
            "general_guidance", PROBLEM_ID, "initial", FORMATTED_PROBLEM,
            target_tokens=1000, lower_bound=950, upper_bound=1050,
        )
        runner._call(
            version0, "general_guidance", PROBLEM_ID, "initial", rendered,
            max_output_tokens=1114,
        )
        self.assertEqual(len(model.calls), 1)
        resumed = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result = resumed._matched_guidance(
            problem_dir, PROBLEM_ID, FORMATTED_PROBLEM, 1000
        )
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(len(model.calls), 2)
        resumed_match = json.loads(
            (problem_dir / "teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(resumed_match["dynamic_max_tokens"], 1164)
        self.assertEqual(resumed_match["versions"][0]["request_max_tokens"], 1114)
        self.assertTrue(resumed_match["versions"][0]["semantic_completeness_passed"])
        again = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result_again = again._matched_guidance(
            problem_dir, PROBLEM_ID, FORMATTED_PROBLEM, 1000
        )
        self.assertEqual(result_again["metrics"], result["metrics"])
        self.assertEqual(len(model.calls), 2)

    def test_semantic_validation_accepts_exact_alias_and_unheaded_forms(self) -> None:
        exact = validate_guidance_content(guidance("COMPLETE"))
        self.assertTrue(exact["preferred_structure"])
        self.assertTrue(exact["semantic_completeness_passed"])
        self.assertEqual(exact["covered_categories"], [
            "constraints", "approaches", "correctness", "implementation"
        ])
        alias = validate_guidance_content(alias_guidance())
        self.assertFalse(alias["preferred_structure"])
        self.assertTrue(alias["semantic_completeness_passed"])
        self.assertIn("preferred_headings_not_used", alias["structural_warnings"])
        unheaded = validate_guidance_content(unheaded_guidance())
        self.assertFalse(unheaded["preferred_structure"])
        self.assertTrue(unheaded["semantic_completeness_passed"])
        blocks = guidance("REORDERED").split("\n\n")
        reordered = validate_guidance_content("\n\n".join(
            [blocks[1], blocks[0], blocks[2], blocks[3]]
        ))
        self.assertFalse(reordered["preferred_structure"])
        self.assertTrue(reordered["semantic_completeness_passed"])

    def test_semantic_validation_rejects_missing_categories_code_and_truncation(self) -> None:
        missing = validate_guidance_content(
            "## Constraints\nInput constraints require O(n) time complexity and "
            "bounded space complexity."
        )
        self.assertFalse(missing["semantic_completeness_passed"])
        self.assertGreaterEqual(len(missing["missing_categories"]), 2)
        one_missing = validate_guidance_content(
            alias_guidance().split("## Implementation Notes", 1)[0].strip()
        )
        self.assertFalse(one_missing["semantic_completeness_passed"])
        self.assertEqual(one_missing["missing_categories"], ["implementation"])
        code = validate_guidance_content(
            unheaded_guidance() + "\n\n```Python\nclass Solution:\n    pass\n```"
        )
        self.assertFalse(code["semantic_completeness_passed"])
        self.assertIn("code_fence_not_allowed", code["structural_errors"])
        unfenced_code = validate_guidance_content(
            unheaded_guidance() +
            "\n\nclass Solution:\n    def solve(self, nums):\n        return len(nums)"
        )
        self.assertFalse(unfenced_code["semantic_completeness_passed"])
        self.assertIn(
            "complete_solution_code_not_allowed",
            unfenced_code["structural_errors"],
        )
        pseudocode = validate_guidance_content(
            unheaded_guidance() + "\n\nThe transition is dp[i] = dp[i-1] + 1."
        )
        self.assertTrue(pseudocode["semantic_completeness_passed"])
        truncated = validate_guidance_content(guidance("ENDS BADLY")[:-1] + ":")
        self.assertFalse(truncated["semantic_completeness_passed"])
        self.assertIn("obviously_incomplete_ending", truncated["structural_errors"])
        unclosed_fence = validate_guidance_content(
            unheaded_guidance() + "\n\n```text\nunfinished"
        )
        self.assertTrue(unclosed_fence["obviously_truncated"])
        self.assertFalse(unclosed_fence["semantic_completeness_passed"])

    def test_successful_api_with_invalid_content_is_not_model_api(self) -> None:
        key = MockModelClient.key
        config = self.config({
            key("teacher", PROBLEM_ID, "teacher"): [item(solver("WA"), 100)],
            key("failure_frontier", PROBLEM_ID, "failure"): [item("FF", 1000)],
            key("general_guidance", PROBLEM_ID, "initial"): [
                item("Generic advice only.", 1000)
            ],
        }, attempts=0)
        runner = PilotRunner(
            config, MockModelClient(config.model), judge=MarkerJudge(),
            project_root=ROOT,
        )
        runner.run("invalid-content")
        record = json.loads(
            (self.root / "runs/invalid-content/problems" / PROBLEM_ID / "record.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(record["valid_episode"])
        self.assertEqual(record["model_output_validation"], "gg_content_validation")
        self.assertNotIn("infrastructure_error", record)

    def full_failure_responses(self, sequence: list[tuple[int, str]]) -> dict:
        key = MockModelClient.key
        responses = {
            key("teacher", PROBLEM_ID, "teacher"): [item(solver("WA"), 100)],
            key("failure_frontier", PROBLEM_ID, "failure"): [
                item("FAILURE FRONTIER", 1110)
            ],
            key("student", PROBLEM_ID, "success_only"): [item(solver("WA"), 100)],
            key("student", PROBLEM_ID, "failure_frontier"): [item(solver("WA"), 100)],
            key("student", PROBLEM_ID, "general_guidance"): [item(solver("WA"), 100)],
        }
        conditions = ["initial", "compress_1", "expand_2"]
        roles = ["general_guidance", "general_guidance_adjust", "general_guidance_adjust"]
        for index, (tokens, marker) in enumerate(sequence):
            responses[key(roles[index], PROBLEM_ID, conditions[index])] = [
                item(guidance(marker), tokens)
            ]
        return responses

    def test_mock_full_chain_oscillation_is_not_comparison_eligible(self) -> None:
        config = self.config(self.full_failure_responses([
            (3026, "V0"), (698, "V1 BEST"), (2884, "V2")
        ]))
        model = MockModelClient(config.model)
        summary = PilotRunner(
            config, model, judge=MarkerJudge(), project_root=ROOT
        ).run("oscillation")
        record = json.loads(
            (self.root / "runs/oscillation/problems" / PROBLEM_ID / "record.json")
            .read_text(encoding="utf-8")
        )
        self.assertTrue(record["token_match_failed"])
        self.assertFalse(record["condition_comparison_eligible"])
        self.assertEqual(record["teaching_material"]["selected_version"], 1)
        self.assertEqual(summary["condition_comparison_ineligible_count"], 1)
        self.assertEqual(summary["teacher_failure_count"], 0)

    def test_mock_full_chain_success_stops_before_third_gg_call(self) -> None:
        config = self.config(self.full_failure_responses([
            (3026, "V0"), (1110, "V1 MATCH")
        ]))
        model = MockModelClient(config.model)
        summary = PilotRunner(
            config, model, judge=MarkerJudge(), project_root=ROOT
        ).run("matched")
        gg_calls = [call for call in model.calls
                    if call["role"].startswith("general_guidance")]
        self.assertEqual(len(gg_calls), 2)
        self.assertEqual(summary["condition_comparison_eligible_count"], 1)
        self.assertEqual(summary["teacher_failure_count"], 1)
        self.assertTrue(all(call["max_output_tokens"] == 1285 for call in gg_calls))
        non_gg = [call for call in model.calls
                  if not call["role"].startswith("general_guidance")]
        self.assertTrue(all(call["max_output_tokens"] == 16384 for call in non_gg))

    def test_recent_smoke_sequence_accepts_semantic_alias_version(self) -> None:
        key = MockModelClient.key
        config = self.config({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("OUTSIDE"), 1290)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(alias_guidance("MATCH"), 1230)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("MUST NOT RUN"), 858)
            ],
        })
        model = MockModelClient(config.model)
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result = runner._matched_guidance(
            self.root / "recent-sequence", PROBLEM_ID, FORMATTED_PROBLEM, 1168
        )
        match = json.loads(
            (self.root / "recent-sequence/teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual((match["lower_bound"], match["upper_bound"]), (1052, 1284))
        self.assertEqual(match["dynamic_max_tokens"], 1348)
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(match["attempts_used"], 2)
        self.assertFalse(match["versions"][1]["preferred_structure"])
        self.assertTrue(match["versions"][1]["semantic_completeness_passed"])
        self.assertTrue(match["versions"][1]["valid_candidate"])
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(len(model.calls), 2)


if __name__ == "__main__":
    unittest.main()
