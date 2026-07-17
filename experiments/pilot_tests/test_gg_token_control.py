from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest

from ffjudge.models import JudgeResult, Verdict

from experiments.pilot.config import load_config
from experiments.pilot.model_client import (
    MockModelClient,
    ModelInfrastructureError,
    ModelResponse,
)
from experiments.pilot.orchestrator import (
    GGContentValidationError,
    PilotRunner,
    condition_comparison_eligible,
    guidance_candidate_state,
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
        "```python\n"
        f"MARKER = {marker!r}\nclass Solution:\n    pass\n"
        "```"
    )


def guidance(marker: str) -> str:
    return (
        "## Constraint Analysis\nThe input size constraints require O(n) time "
        "complexity and bounded space complexity.\n\n"
        "## Algorithmic Directions\nCompare a greedy algorithm with dynamic "
        "programming before selecting an approach.\n\n"
        "## Correctness and Edge Cases\nCheck edge cases and boundaries; use an invariant "
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


def compact_recovery_guidance() -> str:
    return (
        "## Constraints\n- Input constraints require linear time and bounded "
        "space complexity.\n\n"
        "## Approaches\n- Compare a greedy algorithm with dynamic programming.\n\n"
        "## Correctness\n- Use an invariant for correctness and check edge cases.\n\n"
        "## Implementation\n- Check indexing, overflow, and data types."
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


def response(tokens: int, *, finish_reason: str = "stop") -> ModelResponse:
    return ModelResponse(
        content=guidance("STATE"),
        input_tokens=50,
        output_tokens=tokens,
        finish_reason=finish_reason,
        request_id="state",
        seed=None,
        seed_supported=False,
        latency_ms=0,
        token_count_source="mock_usage",
        response_id="state-response",
        returned_model="mock",
        reasoning_content=None,
        total_tokens=50 + tokens,
        request_id_supported=True,
    )


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

    def test_fixed_capacity_does_not_change_acceptance_interval(self) -> None:
        lower, upper = guidance_token_bounds(2043, 0.10)
        self.assertEqual((lower, upper), (1839, 2247))
        self.assertEqual(
            guidance_candidate_state(response(2248), lower, upper, True),
            "COMPLETE_TOO_LONG",
        )
        self.assertEqual(
            guidance_candidate_state(
                response(2697, finish_reason="length"), lower, upper, True
            ),
            "TRUNCATED_TOO_LONG",
        )

    def test_fixed_gg_capacity_is_recorded(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("MATCH"), 2043)
            ],
        }, target=2043)
        self.assertEqual(match["max_output_tokens"], 8192)
        self.assertEqual(match["output_capacity_policy"], {
            "type": "fixed",
            "max_output_tokens": 8192,
        })
        self.assertEqual(model.calls[0]["max_output_tokens"], 8192)
        self.assertNotIn("8192", model.calls[0]["system_prompt"])
        version = match["versions"][0]
        self.assertEqual(version["state"], "MATCHED")
        self.assertIsNone(version["source_version"])
        self.assertEqual(version["source_selection_reason"], "initial_generation")
        self.assertEqual(version["configured_max_tokens"], 8192)
        self.assertEqual(version["request_max_tokens"], 8192)
        self.assertEqual(version["accepted_lower_bound"], 1839)
        self.assertEqual(version["accepted_upper_bound"], 2247)
        self.assertFalse(version["is_complete_long_candidate"])
        self.assertFalse(version["is_complete_short_candidate"])
        self.assertFalse(version["is_truncated_candidate"])
        self.assertIsNone(version["retain_ratio_requested"])
        self.assertIsNone(version["remove_ratio_requested"])
        self.assertIsNone(version["expand_ratio_requested"])
        self.assertIsNone(version["anchor_long_version"])
        self.assertIsNone(version["anchor_short_version"])
        self.assertEqual(match["selected_audit_version"], 0)

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
        self.assertEqual(match["token_interval_outcome"], "matched_within_tolerance")
        self.assertTrue(match["selected_within_token_interval"])
        self.assertFalse(match["fallback_used"])
        self.assertEqual(match["attempts_used"], 1)
        self.assertEqual(len(model.calls), 1)
        version = match["versions"][0]
        self.assertTrue(version["preferred_structure"])
        self.assertTrue(version["semantic_completeness_passed"])
        self.assertTrue(version["valid_candidate"])
        self.assertEqual(match["selected_validation"]["missing_categories"], [])

    def test_too_long_compresses_with_ratios_and_fixed_limit(self) -> None:
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
        self.assertEqual(match["max_output_tokens"], 8192)
        self.assertEqual([call["max_output_tokens"] for call in model.calls],
                         [8192, 8192])
        prompt = model.calls[1]["system_prompt"]
        self.assertIn("50.0%", prompt)
        self.assertIn("editing-only compression", prompt)
        self.assertIn("delete repetition", prompt)
        self.assertIn("merge overlapping passages", prompt)
        self.assertIn("abbreviate or condense wording", prompt)
        self.assertIn("Do not introduce any new content", prompt)

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
        self.assertEqual(
            [call["max_output_tokens"] for call in model.calls], [8192, 8192]
        )

    def test_complete_long_compresses_to_match_with_new_capacity(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("COMPLETE LONG"), 2500)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("MATCH"), 2040)
            ],
        }, target=2043)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(match["best_complete_long_version"], 0)
        self.assertEqual(match["versions"][0]["state"], "COMPLETE_TOO_LONG")
        self.assertEqual(match["versions"][1]["state"], "MATCHED")
        self.assertEqual(match["versions"][1]["source_version"], 0)
        self.assertEqual([call["max_output_tokens"] for call in model.calls],
                         [8192, 8192])
        self.assertIn("81.7%", model.calls[1]["system_prompt"])
        self.assertIn("18.3%", model.calls[1]["system_prompt"])

    def test_truncated_initial_uses_compact_recovery_prompt_without_source_text(self) -> None:
        key = MockModelClient.key
        truncated_marker = "TRUNCATED_SOURCE_MUST_NOT_BE_COPIED"
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance(truncated_marker), 2697, finish_reason="length")
            ],
            key("general_guidance_adjust", PROBLEM_ID, "truncation_recovery_1"): [
                item(guidance("FRESH MATCH"), 2040)
            ],
        }, target=2043, attempts=1)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["versions"][0]["state"], "TRUNCATED_TOO_LONG")
        self.assertFalse(match["versions"][0]["is_complete_long_candidate"])
        self.assertTrue(match["versions"][0]["is_truncated_candidate"])
        self.assertEqual(match["versions"][1]["operation"], "truncation_recovery")
        self.assertIsNone(match["versions"][1]["source_version"])
        self.assertEqual(
            match["versions"][1]["source_selection_reason"],
            "truncation_recovery_from_problem",
        )
        self.assertTrue(match["truncation_recovery_used"])
        self.assertNotIn(truncated_marker, model.calls[1]["user_prompt"])
        self.assertEqual(model.calls[1]["user_prompt"], FORMATTED_PROBLEM)
        recovery_prompt = model.calls[1]["system_prompt"]
        self.assertIn("exhausted the full output capacity", recovery_prompt)
        self.assertIn("Do not perform open-ended exploration", recovery_prompt)
        self.assertIn("## Constraints", recovery_prompt)
        self.assertIn("## Approaches", recovery_prompt)
        self.assertIn("## Correctness", recovery_prompt)
        self.assertIn("## Implementation", recovery_prompt)
        self.assertIn("3 bullets per section", recovery_prompt)
        self.assertIn("2 sentences per bullet", recovery_prompt)
        self.assertIn("2 algorithmic directions total", recovery_prompt)
        self.assertIn("Do not narrate your thought process", recovery_prompt)
        self.assertIn("Do not include code", recovery_prompt)
        self.assertEqual(
            [call["max_output_tokens"] for call in model.calls], [8192, 8192]
        )

    def test_long_short_interpolation_reuses_long_anchor_and_matches(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG_ANCHOR"), 2500)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("SHORT_ANCHOR"), 1189)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("INTERPOLATED MATCH"), 2050)
            ],
        }, target=2043)
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 2)
        self.assertEqual(match["best_complete_long_version"], 0)
        self.assertEqual(match["best_complete_short_version"], 1)
        third = match["versions"][2]
        self.assertEqual(third["source_version"], 0)
        self.assertEqual(third["anchor_long_version"], 0)
        self.assertEqual(third["anchor_short_version"], 1)
        self.assertEqual(
            third["ratio_strategy"],
            "linear_correction_from_complete_long_and_short",
        )
        self.assertAlmostEqual(third["retain_ratio_requested"], 0.9363, places=3)
        self.assertIn("LONG_ANCHOR", model.calls[2]["user_prompt"])
        self.assertNotIn("SHORT_ANCHOR", model.calls[2]["user_prompt"])
        self.assertIn("93.6%", model.calls[2]["system_prompt"])

    def test_second_compression_uses_invalid_first_attempt_feedback(self) -> None:
        key = MockModelClient.key
        missing_implementation = guidance("FIRST OVER-COMPRESSION").split(
            "## Implementation Checks", 1
        )[0].strip()
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG SOURCE"), 1857)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(missing_implementation, 693)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("REPAIRED MATCH"), 1200)
            ],
        }, target=1192)

        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(match["matched_version"], 2)
        self.assertEqual(match["versions"][1]["state"], "INVALID_CONTENT")
        second = match["versions"][2]
        self.assertEqual(second["source_version"], 0)
        self.assertEqual(second["feedback_source_version"], 1)
        self.assertAlmostEqual(
            second["retain_ratio_requested"], 0.7954128245, places=6
        )
        self.assertEqual(
            second["ratio_strategy"],
            "linear_correction_from_previous_invalid_compression",
        )
        prompt = model.calls[2]["system_prompt"]
        self.assertIn(
            "The previous compressed version was invalid because it omitted "
            "substantive implementation coverage.",
            prompt,
        )
        self.assertIn(
            "allocate approximately 20% of the response to implementation checks",
            prompt,
        )
        self.assertIn("Do not repeat the previous over-compression.", prompt)
        self.assertIn("79.5%", prompt)
        self.assertIn("LONG SOURCE", model.calls[2]["user_prompt"])
        self.assertNotIn("FIRST OVER-COMPRESSION", model.calls[2]["user_prompt"])

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

    def test_all_failed_oscillation_selects_closest_to_target(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("V0"), 3026)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("V1 BEST"), 698)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("V2"), 2884)
            ],
        }, target=1110)
        self.assertFalse(result["metrics"]["token_match_passed"])
        self.assertTrue(result["metrics"]["token_match_failed"])
        self.assertEqual(result["response"].output_tokens, 698)
        self.assertEqual(match["selected_version"], 1)
        self.assertEqual(match["selection_reason"],
                         "fallback_closest_to_ff_target")
        self.assertTrue(match["fallback_used"])
        self.assertEqual(
            match["token_interval_outcome"], "fallback_outside_tolerance"
        )
        self.assertFalse(match["selected_within_token_interval"])
        self.assertEqual([v["completion_tokens"] for v in match["versions"]],
                         [3026, 698, 2884])
        self.assertEqual(len(model.calls), 3)
        self.assertIn("50.0%", model.calls[1]["system_prompt"])
        self.assertEqual(match["versions"][2]["source_version"], 0)
        self.assertEqual(
            match["versions"][2]["source_selection_reason"],
            "compress_best_complete_long_candidate",
        )
        self.assertNotIn("longer", model.calls[2]["system_prompt"])

    def test_all_failed_fallback_selects_closest_when_all_are_below(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("V0"), 400)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_1"): [
                item(guidance("V1"), 700)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "expand_2"): [
                item(guidance("V2"), 850)
            ],
        }, target=1000)
        self.assertFalse(result["metrics"]["token_match_passed"])
        self.assertTrue(result["metrics"]["fallback_used"])
        self.assertEqual(result["response"].output_tokens, 850)
        self.assertEqual(match["selected_version"], 2)
        self.assertEqual(
            match["selection_reason"],
            "fallback_closest_to_ff_target",
        )
        self.assertEqual(
            match["fallback_selection_policy"],
            "minimum_absolute_distance_to_ff_target",
        )
        self.assertEqual(len(model.calls), 3)

    def test_truncated_sequence_fallback_selects_closest_to_target(self) -> None:
        key = MockModelClient.key
        result, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("TRUNCATED V0"), 2697, finish_reason="length")
            ],
            key("general_guidance_adjust", PROBLEM_ID, "truncation_recovery_1"): [
                item(guidance("SHORT V1"), 1189)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "truncation_recovery_2"): [
                item(guidance("TRUNCATED V2"), 2697, finish_reason="length")
            ],
        }, target=2043)
        self.assertFalse(result["metrics"]["token_match_passed"])
        self.assertEqual(match["selected_audit_version"], 0)
        self.assertTrue(match["fallback_used"])
        self.assertEqual(
            match["selection_reason"],
            "fallback_closest_to_ff_target",
        )
        self.assertEqual(match["best_complete_long_version"], None)
        self.assertEqual(match["best_complete_short_version"], 1)
        self.assertEqual(
            [item["state"] for item in match["versions"]],
            ["TRUNCATED_TOO_LONG", "TOO_SHORT", "TRUNCATED_TOO_LONG"],
        )
        self.assertIsNone(match["versions"][2]["source_version"])
        self.assertEqual(match["versions"][2]["operation"], "truncation_recovery")
        self.assertEqual(len(model.calls), 3)

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
        self.assertEqual(match["token_interval_outcome"], "unmatched_no_fallback")
        self.assertFalse(match["selected_within_token_interval"])
        self.assertIsNone(match["selected_version"])
        self.assertEqual(match["versions"][0]["status"],
                         "TRUNCATED_TOO_LONG")
        self.assertFalse(match["versions"][0]["valid_candidate"])
        self.assertTrue(match["versions"][0]["is_truncated_candidate"])
        self.assertIsNone(match["selected_audit_version"])

    def test_length_finish_can_use_one_remaining_adjustment(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("TRUNCATED"), 1000, finish_reason="length")
            ],
            key("general_guidance_adjust", PROBLEM_ID, "truncation_recovery_1"): [
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

    def test_initial_adjustment_and_recovery_prompts_are_isolated(self) -> None:
        config = self.config({})
        runner = PilotRunner(
            config, MockModelClient(config.model), judge=NoJudge(),
            project_root=ROOT,
        )
        calls = [runner._rendered_call(
            "general_guidance", PROBLEM_ID, "initial", FORMATTED_PROBLEM,
            target_tokens=2043, lower_bound=1839, upper_bound=2247,
        )]
        for direction in ("compress", "expand"):
            calls.append(runner._rendered_call(
                "general_guidance_adjust", PROBLEM_ID, f"{direction}_1",
                FORMATTED_PROBLEM,
                target_tokens=2043, lower_bound=1839, upper_bound=2247,
                source_tokens=2500, retain_ratio_percent="81.7",
                remove_ratio_percent="18.3", expand_ratio_percent="71.8",
                general_guidance=guidance("SAFE SOURCE"), direction=direction,
            ))
        calls.append(runner._rendered_call(
            "general_guidance_adjust", PROBLEM_ID, "regenerate_1",
            FORMATTED_PROBLEM,
            target_tokens=2043, lower_bound=1839, upper_bound=2247,
            direction="regenerate",
        ))
        calls.append(runner._rendered_call(
            "general_guidance_adjust", PROBLEM_ID, "truncation_recovery_1",
            FORMATTED_PROBLEM,
            target_tokens=2043, lower_bound=1839, upper_bound=2247,
            direction="truncation_recovery",
        ))
        forbidden = (
            "TEACHER_RESPONSE_SENTINEL", "TEACHER_CODE_SENTINEL",
            "VERDICT_SENTINEL", "FF_MATERIAL_SENTINEL",
            "HIDDEN_TEST_SENTINEL", "JUDGE_SENTINEL",
        )
        for call in calls:
            visible = call["system_prompt"] + "\n" + call["user_prompt"]
            self.assertFalse(any(item in visible for item in forbidden))
            self.assertIn(FORMATTED_PROBLEM, call["user_prompt"])
        self.assertIn("Complete the response naturally", calls[0]["system_prompt"])
        self.assertNotIn("8192", calls[0]["system_prompt"])
        self.assertIn(
            "The previous generation exhausted the full output capacity",
            calls[-1]["system_prompt"],
        )
        self.assertIn("3 bullets per section", calls[-1]["system_prompt"])
        self.assertEqual(calls[-1]["user_prompt"], FORMATTED_PROBLEM)

    def test_total_calls_never_exceed_initial_plus_adjustments(self) -> None:
        key = MockModelClient.key
        _, match, model, _ = self.direct({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("V0"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("V1"), 600)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
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
            target_tokens=1000, lower_bound=900, upper_bound=1100,
        )
        rendered["system_prompt"] += "\nLEGACY GG PROMPT SCHEMA"
        runner._call(
            version0, "general_guidance", PROBLEM_ID, "initial", rendered,
            max_output_tokens=1114,
        )
        (version0 / "version.json").write_text(
            json.dumps({"version": 0, "status": "TOO_LONG"}),
            encoding="utf-8",
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
        self.assertEqual(resumed_match["max_output_tokens"], 8192)
        self.assertEqual(
            resumed_match["versions"][0]["configured_max_tokens"], 8192
        )
        self.assertEqual(resumed_match["versions"][0]["request_max_tokens"], 1114)
        self.assertTrue(resumed_match["versions"][0]["semantic_completeness_passed"])
        self.assertIn(
            "persisted_legacy_prompt_mismatch_reused",
            resumed_match["compatibility_warnings"],
        )
        self.assertIn(
            "persisted_legacy_version_schema_reconstructed",
            resumed_match["compatibility_warnings"],
        )
        again = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result_again = again._matched_guidance(
            problem_dir, PROBLEM_ID, FORMATTED_PROBLEM, 1000
        )
        self.assertEqual(result_again["metrics"], result["metrics"])
        self.assertEqual(len(model.calls), 2)

    def test_resume_preserves_legacy_adjustment_source_metadata(self) -> None:
        key = MockModelClient.key
        responses = {
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("LONG"), 3000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(guidance("SHORT"), 600)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("MATCH"), 1000)
            ],
        }
        config = self.config(responses)
        model = MockModelClient(config.model)
        problem_dir = self.root / "problem"
        stage_root = problem_dir / "teaching_materials/general_guidance"
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        for version, role, condition in (
            (0, "general_guidance", "initial"),
            (1, "general_guidance_adjust", "compress_1"),
        ):
            runner._call(
                stage_root / f"version_{version}", role, PROBLEM_ID, condition,
                {
                    "role": role,
                    "problem_id": PROBLEM_ID,
                    "condition": condition,
                    "system_prompt": f"LEGACY SYSTEM {version}",
                    "user_prompt": f"LEGACY USER {version}",
                },
                max_output_tokens=1114,
            )
        (stage_root / "version_0/version.json").write_text(
            json.dumps({"version": 0, "status": "TOO_LONG"}),
            encoding="utf-8",
        )
        (stage_root / "version_1/version.json").write_text(
            json.dumps({
                "version": 1,
                "operation": "compress",
                "input_version": 0,
                "status": "TOO_SHORT",
            }),
            encoding="utf-8",
        )

        resumed = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result = resumed._matched_guidance(
            problem_dir, PROBLEM_ID, FORMATTED_PROBLEM, 1000
        )

        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(len(model.calls), 3)
        match = json.loads(
            (stage_root / "match.json").read_text(encoding="utf-8")
        )
        legacy_adjustment = match["versions"][1]
        self.assertEqual(legacy_adjustment["operation"], "compress")
        self.assertEqual(legacy_adjustment["source_version"], 0)
        self.assertEqual(
            legacy_adjustment["source_selection_reason"],
            "persisted_legacy_previous_version_source_inferred",
        )
        self.assertIsNone(legacy_adjustment["retain_ratio_requested"])
        self.assertIn(
            "persisted_legacy_ratio_metadata_unavailable",
            legacy_adjustment["compatibility_warnings"],
        )
        self.assertEqual(match["versions"][2]["source_version"], 0)

    def test_semantic_validation_accepts_complete_content_without_exact_headings(self) -> None:
        exact = validate_guidance_content(guidance("COMPLETE"))
        self.assertTrue(exact["preferred_structure"])
        self.assertTrue(exact["required_sections_passed"])
        self.assertTrue(exact["semantic_completeness_passed"])
        self.assertEqual(exact["covered_categories"], [
            "constraints", "approaches", "correctness", "implementation"
        ])
        alias = validate_guidance_content(alias_guidance())
        self.assertFalse(alias["preferred_structure"])
        self.assertTrue(alias["required_sections_passed"])
        self.assertTrue(alias["semantic_completeness_passed"])
        self.assertIn(
            "preferred_sections_missing_or_reordered",
            alias["structural_warnings"],
        )
        self.assertEqual(alias["structural_errors"], [])
        unheaded = validate_guidance_content(unheaded_guidance())
        self.assertFalse(unheaded["preferred_structure"])
        self.assertTrue(unheaded["required_sections_passed"])
        self.assertTrue(unheaded["semantic_completeness_passed"])
        blocks = guidance("REORDERED").split("\n\n")
        reordered = validate_guidance_content("\n\n".join(
            [blocks[1], blocks[0], blocks[2], blocks[3]]
        ))
        self.assertFalse(reordered["preferred_structure"])
        self.assertTrue(reordered["required_sections_passed"])
        self.assertTrue(reordered["semantic_completeness_passed"])
        recovery = validate_guidance_content(compact_recovery_guidance())
        self.assertFalse(recovery["preferred_structure"])
        self.assertTrue(recovery["required_sections_passed"])
        self.assertTrue(recovery["semantic_completeness_passed"])
        self.assertEqual(recovery["missing_categories"], [])

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
            guidance("The transition is dp[i] = dp[i-1] + 1")
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
        self.assertFalse(record["condition_comparison_eligible"])
        self.assertEqual(record["model_output_validation"], "gg_content_validation")
        self.assertNotIn("infrastructure_error", record)

    def test_truncated_outside_interval_uses_ineligible_fallback_not_model_api(self) -> None:
        config = self.config(self.full_failure_responses([
            (1356, "TRUNCATED V0", "length"),
            (1400, "TRUNCATED V1", "length"),
            (1380, "TRUNCATED V2", "length"),
        ], target=1000, conditions=[
            "initial", "truncation_recovery_1", "truncation_recovery_2"
        ]))
        runner = PilotRunner(
            config, MockModelClient(config.model), judge=MarkerJudge(),
            project_root=ROOT,
        )
        runner.run("truncated-only")
        record = json.loads(
            (self.root / "runs/truncated-only/problems" / PROBLEM_ID / "record.json")
            .read_text(encoding="utf-8")
        )
        self.assertTrue(record["valid_episode"])
        self.assertFalse(record["condition_comparison_eligible"])
        self.assertTrue(record["token_match_failed"])
        self.assertEqual(record["teaching_material"]["selected_version"], 0)
        self.assertTrue(record["teaching_material"]["fallback_used"])
        self.assertEqual(
            record["teaching_material"]["token_interval_outcome"],
            "fallback_outside_tolerance",
        )
        self.assertTrue(record["teaching_material"]["truncation_recovery_used"])
        self.assertTrue(record["teaching_material"]["general_guidance_truncated"])
        self.assertEqual(len(record["students"]), 3)
        self.assertNotIn("model_output_validation", record)
        self.assertNotIn("infrastructure_error", record)

    def full_failure_responses(
        self,
        sequence: list[tuple[int, str] | tuple[int, str, str]],
        *,
        target: int = 1110,
        conditions: list[str] | None = None,
    ) -> dict:
        key = MockModelClient.key
        responses = {
            key("teacher", PROBLEM_ID, "teacher"): [item(solver("WA"), 100)],
            key("failure_frontier", PROBLEM_ID, "failure"): [
                item("FAILURE FRONTIER", target)
            ],
            key("student", PROBLEM_ID, "success_only"): [item(solver("WA"), 100)],
            key("student", PROBLEM_ID, "failure_frontier"): [item(solver("WA"), 100)],
            key("student", PROBLEM_ID, "general_guidance"): [item(solver("WA"), 100)],
        }
        conditions = conditions or ["initial", "compress_1", "compress_2"]
        roles = ["general_guidance", "general_guidance_adjust", "general_guidance_adjust"]
        for index, entry in enumerate(sequence):
            tokens, marker = entry[:2]
            finish_reason = entry[2] if len(entry) == 3 else "stop"
            responses[key(roles[index], PROBLEM_ID, conditions[index])] = [
                item(guidance(marker), tokens, finish_reason=finish_reason)
            ]
        return responses

    def test_mock_full_chain_oscillation_is_not_comparison_eligible(self) -> None:
        config = self.config(self.full_failure_responses([
            (3026, "V0"), (698, "V1 CLOSEST"), (2884, "V2")
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
        self.assertTrue(record["teaching_material"]["fallback_used"])
        self.assertEqual(summary["condition_comparison_ineligible_count"], 1)
        self.assertEqual(summary["teacher_failure_count"], 0)
        self.assertEqual(
            summary["token_matching"]["fallback_outside_tolerance_count"], 1
        )
        self.assertEqual(
            summary["token_matching"]["matched_within_tolerance_count"], 0
        )

    def test_mock_full_chain_success_stops_before_third_gg_call(self) -> None:
        config = self.config(self.full_failure_responses([
            (2500, "V0 COMPLETE LONG"), (2040, "V1 MATCH")
        ], target=2043))
        model = MockModelClient(config.model)
        summary = PilotRunner(
            config, model, judge=MarkerJudge(), project_root=ROOT
        ).run("matched")
        gg_calls = [call for call in model.calls
                    if call["role"].startswith("general_guidance")]
        self.assertEqual(len(gg_calls), 2)
        self.assertEqual(summary["condition_comparison_eligible_count"], 1)
        self.assertEqual(summary["teacher_failure_count"], 1)
        self.assertEqual(
            summary["token_matching"]["matched_within_tolerance_count"], 1
        )
        self.assertEqual(
            summary["token_matching"]["fallback_outside_tolerance_count"], 0
        )
        self.assertTrue(all(call["max_output_tokens"] == 8192 for call in gg_calls))
        planning_calls = [call for call in model.calls
                          if call["role"].endswith("_planning")]
        final_calls = [call for call in model.calls
                       if call["role"].endswith("_final")]
        solver_calls = planning_calls + final_calls
        material_calls = [call for call in model.calls
                          if not call["role"].startswith("general_guidance") and
                          call not in solver_calls]
        self.assertTrue(all(call["max_output_tokens"] == 2048
                            for call in planning_calls))
        self.assertTrue(all(call["max_output_tokens"] == 8192
                            for call in final_calls))
        self.assertTrue(all(call["max_output_tokens"] == 16384
                            for call in material_calls))

    def test_mock_full_chain_long_short_interpolation_matches_from_long(self) -> None:
        config = self.config(self.full_failure_responses([
            (2500, "LONG_ANCHOR"),
            (1189, "SHORT_ANCHOR"),
            (2050, "V2 MATCH"),
        ], target=2043))
        model = MockModelClient(config.model)
        summary = PilotRunner(
            config, model, judge=MarkerJudge(), project_root=ROOT
        ).run("interpolation")
        record = json.loads(
            (self.root / "runs/interpolation/problems" / PROBLEM_ID / "record.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(summary["condition_comparison_eligible_count"], 1)
        self.assertEqual(record["teaching_material"]["matched_version"], 2)
        match = json.loads(
            (self.root / "runs/interpolation/problems" / PROBLEM_ID /
             "teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(match["versions"][2]["source_version"], 0)
        gg_calls = [call for call in model.calls
                    if call["role"].startswith("general_guidance")]
        self.assertIn("LONG_ANCHOR", gg_calls[2]["user_prompt"])
        self.assertNotIn("SHORT_ANCHOR", gg_calls[2]["user_prompt"])

    def test_mock_full_chain_truncated_sequence_is_not_comparison_eligible(self) -> None:
        config = self.config(self.full_failure_responses([
            (2697, "TRUNCATED V0", "length"),
            (1189, "SHORT V1", "stop"),
            (2697, "TRUNCATED V2", "length"),
        ], target=2043, conditions=[
            "initial", "truncation_recovery_1", "truncation_recovery_2"
        ]))
        model = MockModelClient(config.model)
        summary = PilotRunner(
            config, model, judge=MarkerJudge(), project_root=ROOT
        ).run("truncated-chain")
        record = json.loads(
            (self.root / "runs/truncated-chain/problems" / PROBLEM_ID /
             "record.json").read_text(encoding="utf-8")
        )
        self.assertTrue(record["token_match_failed"])
        self.assertFalse(record["condition_comparison_eligible"])
        self.assertEqual(record["teaching_material"]["selected_audit_version"], 0)
        self.assertTrue(record["teaching_material"]["fallback_used"])
        self.assertEqual(
            record["teaching_material"]["token_interval_outcome"],
            "fallback_outside_tolerance",
        )
        self.assertTrue(record["teaching_material"]["truncation_recovery_used"])
        self.assertEqual(summary["condition_comparison_ineligible_count"], 1)

    def test_alias_sections_match_without_exact_heading_retry(self) -> None:
        key = MockModelClient.key
        config = self.config({
            key("general_guidance", PROBLEM_ID, "initial"): [
                item(guidance("OUTSIDE"), 1290)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                item(alias_guidance("MATCH"), 1230)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_2"): [
                item(guidance("EXACT MATCH"), 1230)
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
        self.assertEqual(match["max_output_tokens"], 8192)
        self.assertEqual(match["matched_version"], 1)
        self.assertEqual(match["attempts_used"], 2)
        self.assertFalse(match["versions"][1]["preferred_structure"])
        self.assertTrue(match["versions"][1]["required_sections_passed"])
        self.assertTrue(match["versions"][1]["semantic_completeness_passed"])
        self.assertTrue(match["versions"][1]["valid_candidate"])
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(len(model.calls), 2)

    def test_condition_comparison_eligibility_invariant(self) -> None:
        self.assertTrue(condition_comparison_eligible({"valid_episode": True}))
        for disqualifier in (
            {"valid_episode": False},
            {"valid_episode": True, "infrastructure_error": "judge"},
            {"valid_episode": True, "protocol_output_invalid": True},
            {"valid_episode": True, "token_match_failed": True},
        ):
            with self.subTest(record=disqualifier):
                self.assertFalse(condition_comparison_eligible(disqualifier))

    def test_resume_rederives_condition_comparison_eligibility(self) -> None:
        config = self.config({})
        model = MockModelClient(config.model)
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        runner.run_dir = self.root / "resume-run"
        record_path = (
            runner.run_dir / "problems" / PROBLEM_ID / "record.json"
        )
        record_path.parent.mkdir(parents=True)
        record_path.write_text(json.dumps({
            "run_id": "resume-run",
            "problem_id": PROBLEM_ID,
            "valid_episode": False,
            "condition_comparison_eligible": True,
            "protocol_output_invalid": True,
        }), encoding="utf-8")

        resumed = runner._run_problem("resume-run", config.problems[0])

        self.assertFalse(resumed["condition_comparison_eligible"])
        persisted = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertFalse(persisted["condition_comparison_eligible"])
        self.assertEqual(model.calls, [])


if __name__ == "__main__":
    unittest.main()
