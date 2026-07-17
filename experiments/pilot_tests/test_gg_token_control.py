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
        "## Constraint Analysis\nPreserve the important constraints.\n\n"
        "## Plausible Approaches\nCompare suitable algorithmic directions.\n\n"
        "## Edge Cases\nHandle boundaries and degenerate inputs.\n\n"
        f"## Implementation Checks\n{marker}."
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
        self.assertEqual(guidance_token_bounds(1110, 0.05), (1055, 1165))
        self.assertEqual(guidance_distance_to_interval(1054, 1055, 1165), 1)
        self.assertEqual(guidance_distance_to_interval(1110, 1055, 1165), 0)
        self.assertEqual(guidance_distance_to_interval(1166, 1055, 1165), 1)

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
        self.assertEqual(match["dynamic_max_tokens"], 1114)
        self.assertEqual([call["max_output_tokens"] for call in model.calls],
                         [1114, 1114])
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
        with self.assertRaisesRegex(ModelInfrastructureError, "no complete"):
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
        again = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        result_again = again._matched_guidance(
            problem_dir, PROBLEM_ID, FORMATTED_PROBLEM, 1000
        )
        self.assertEqual(result_again["metrics"], result["metrics"])
        self.assertEqual(len(model.calls), 2)

    def test_structural_validation_rejects_missing_or_truncated_sections(self) -> None:
        self.assertEqual(validate_guidance_content(guidance("COMPLETE")), (True, []))
        valid, errors = validate_guidance_content(
            "## Constraint Analysis\nOnly one section."
        )
        self.assertFalse(valid)
        self.assertIn("missing_required_section", errors)
        valid, errors = validate_guidance_content(
            guidance("ENDS BADLY")[:-1] + ":"
        )
        self.assertFalse(valid)
        self.assertIn("obviously_incomplete_ending", errors)

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
        self.assertTrue(all(call["max_output_tokens"] == 1229 for call in gg_calls))
        non_gg = [call for call in model.calls
                  if not call["role"].startswith("general_guidance")]
        self.assertTrue(all(call["max_output_tokens"] == 8192 for call in non_gg))


if __name__ == "__main__":
    unittest.main()
