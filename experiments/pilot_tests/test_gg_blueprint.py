from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest

from experiments.pilot.config import load_config
from experiments.pilot.gg_controller import (
    duplicate_material_request,
    material_paragraph_budgets,
    material_section_budgets,
    select_material_fallback,
    validate_blueprint_response,
)
from experiments.pilot.model_client import MockModelClient
from experiments.pilot.orchestrator import (
    GGContentValidationError,
    PilotRunner,
)


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "experiments/configs/pilot_v1.yaml"
PROBLEM_ID = "lc-0009-palindrome-number"
PUBLIC_PROBLEM = "PUBLIC PROBLEM ONLY"


def blueprint() -> dict:
    return {
        "constraints": [
            {"point": "Respect the public input bound.",
             "importance": "It determines the required complexity."},
            {"point": "Handle the smallest public input.",
             "importance": "It fixes the base case."},
        ],
        "approaches": [
            {"name": "Invariant scan", "core_idea": "Maintain a bounded state.",
             "why_plausible": "The public bounds permit one pass.",
             "main_risk": "A boundary transition may be wrong."},
        ],
        "correctness": [
            {"claim": "Each transition preserves the invariant.",
             "check": "Check every transition case."},
            {"claim": "The terminal state gives the answer.",
             "check": "Check initialization and termination."},
        ],
        "implementation": [
            {"risk": "Indexing can be off by one.",
             "check": "Audit both boundaries."},
            {"risk": "Initialization can omit a state.",
             "check": "Test the minimum input."},
            {"risk": "Arithmetic can overflow.",
             "check": "Use a safe numeric type."},
        ],
    }


def guidance(marker: str = "MATERIAL") -> str:
    return (
        "## Constraint Analysis\nInput constraints require O(n) time complexity "
        "and bounded space complexity.\n\n"
        "## Algorithmic Directions\nUse an invariant scan algorithm and maintain "
        "the selected state transition.\n\n"
        "## Correctness and Edge Cases\nProve the invariant and check edge cases "
        "and both boundaries.\n\n"
        "## Implementation Checks\nAudit data structures, indexing, initialization, "
        f"overflow, and complexity risks. {marker}."
    )


def item(content: str, tokens: int, finish_reason: str = "stop") -> dict:
    return {
        "content": content,
        "input_tokens": 20,
        "output_tokens": tokens,
        "total_tokens": tokens + 20,
        "finish_reason": finish_reason,
    }


class NoJudge:
    def judge(self, *args, **kwargs):
        raise AssertionError("GG tests must not access the judge")


class GeneralGuidanceBlueprintTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def config(self, responses: dict[str, list[dict]]):
        response_path = self.root / "responses.json"
        response_path.write_text(json.dumps(responses), encoding="utf-8")
        base = load_config(CONFIG)
        return replace(
            base,
            problems=(base.problems[0],),
            model=replace(base.model, mock_responses_path=str(response_path)),
            execution=replace(base.execution, output_root=str(self.root / "runs")),
            prompts_dir=str(ROOT / "experiments/prompts"),
            baseline_manifest=str(
                ROOT / "experiments/baseline_v2/baseline_manifest.json"
            ),
        )

    def runner(self, responses: dict[str, list[dict]]):
        config = self.config(responses)
        model = MockModelClient(config.model)
        runner = PilotRunner(config, model, judge=NoJudge(), project_root=ROOT)
        return runner, model

    def test_blueprint_schema_accepts_valid_json(self) -> None:
        result = validate_blueprint_response(json.dumps(blueprint()), "stop")
        self.assertEqual(result["status"], "BLUEPRINT_VALID")
        self.assertTrue(result["valid"])

    def test_blueprint_schema_rejects_missing_category(self) -> None:
        value = blueprint()
        del value["implementation"]
        result = validate_blueprint_response(json.dumps(value), "stop")
        self.assertEqual(result["status"], "BLUEPRINT_INVALID_SCHEMA")
        self.assertIn("top_level_categories_invalid", result["errors"])

    def test_blueprint_schema_rejects_too_many_approaches(self) -> None:
        value = blueprint()
        value["approaches"] *= 3
        result = validate_blueprint_response(json.dumps(value), "stop")
        self.assertEqual(result["status"], "BLUEPRINT_INVALID_SCHEMA")
        self.assertIn("approaches_item_count_invalid", result["errors"])

    def test_blueprint_schema_rejects_code_fence_and_solution_code(self) -> None:
        fenced = json.dumps(blueprint()).replace(
            "Respect the public input bound.", "```python class Solution: pass ```"
        )
        self.assertEqual(
            validate_blueprint_response(fenced, "stop")["status"],
            "BLUEPRINT_FORBIDDEN_CONTENT",
        )
        value = blueprint()
        value["constraints"][0]["point"] = "Define def solve(x) as the submission."
        self.assertEqual(
            validate_blueprint_response(json.dumps(value), "stop")["status"],
            "BLUEPRINT_FORBIDDEN_CONTENT",
        )

    def test_blueprint_schema_rejects_length_finish(self) -> None:
        result = validate_blueprint_response(json.dumps(blueprint()), "length")
        self.assertEqual(result["status"], "BLUEPRINT_TRUNCATED")
        self.assertFalse(result["valid"])

    def test_blueprint_repair_then_material_match(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item("not json", 30)
            ],
            key("general_guidance_blueprint_repair", PROBLEM_ID, "blueprint_repair"): [
                item(json.dumps(blueprint()), 150)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item(guidance(), 1000)
            ],
        })
        result = runner._matched_guidance(
            self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
        )
        self.assertTrue(result["metrics"]["token_match_passed"])
        self.assertEqual(result["metrics"]["blueprint_attempts_used"], 2)
        self.assertEqual(
            [call["role"] for call in model.calls],
            ["general_guidance_blueprint", "general_guidance_blueprint_repair",
             "general_guidance"],
        )
        self.assertNotIn("not json", model.calls[1]["system_prompt"])
        self.assertNotIn("not json", model.calls[1]["user_prompt"])
        self.assertIn("invalid_json", model.calls[1]["system_prompt"])
        blueprint_root = (
            self.root / "problem/teaching_materials/general_guidance/blueprint"
        )
        for name in ("request.json", "response.json", "blueprint.json",
                     "validation.json", "selection.json"):
            self.assertTrue((blueprint_root / name).is_file())

    def test_all_blueprints_fail_without_material_call(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item("bad", 10)
            ],
            key("general_guidance_blueprint_repair", PROBLEM_ID, "blueprint_repair"): [
                item("still bad", 12)
            ],
        })
        with self.assertRaises(GGContentValidationError) as caught:
            runner._matched_guidance(
                self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
            )
        self.assertEqual(caught.exception.validation_error, "gg_blueprint_invalid")
        self.assertEqual(len(model.calls), 2)
        self.assertFalse(any(call["role"] == "general_guidance" for call in model.calls))
        self.assertFalse((self.root / "problem/teaching_materials/general_guidance/version_0").exists())

    def test_blueprint_tokens_do_not_participate_in_matching(self) -> None:
        key = MockModelClient.key
        runner, _ = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item(json.dumps(blueprint()), 999)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item(guidance(), 1000)
            ],
        })
        result = runner._matched_guidance(
            self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
        )
        self.assertEqual(result["metrics"]["general_guidance_tokens"], 1000)
        match = json.loads(
            (self.root / "problem/teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(match["blueprint_completion_tokens"], 999)
        self.assertEqual(match["versions"][0]["completion_tokens"], 1000)
        version = match["versions"][0]
        for field in (
            "prompt_hash", "prompt_type", "source_blueprint_version",
            "source_material_version", "recovery_mode", "section_budget",
            "paragraph_budget", "requested_retain_ratio",
            "missing_categories_feedback", "previous_candidate_tokens",
            "duplicate_prompt_prevented", "contains_forbidden_content",
        ):
            self.assertIn(field, version)
        self.assertEqual(match["gg_generation_policy"], "blueprint_render_v1")
        self.assertEqual(match["strict_candidate_versions"], [0])
        self.assertEqual(match["complete_semantic_candidate_versions"], [0])

    def test_budget_functions_are_deterministic(self) -> None:
        self.assertEqual(material_section_budgets(4092), {
            "constraints": 614,
            "approaches": 1841,
            "correctness": 818,
            "implementation": 819,
        })
        self.assertEqual(
            material_paragraph_budgets(1600)["max_paragraphs_per_section"], 2
        )
        self.assertEqual(
            material_paragraph_budgets(1601)["max_paragraphs_per_section"], 3
        )
        self.assertEqual(
            material_paragraph_budgets(3501)["max_paragraphs_per_section"], 4
        )

    def test_fallback_excludes_truncated_invalid_and_forbidden(self) -> None:
        records = [
            {"version": 0, "completion_tokens": 1600, "finish_reason": "stop",
             "semantic_completeness_passed": True, "forbidden_content": [],
             "state": "COMPLETE_TOO_LONG"},
            {"version": 1, "completion_tokens": 900, "finish_reason": "stop",
             "semantic_completeness_passed": True, "forbidden_content": [],
             "state": "TOO_SHORT"},
            {"version": 2, "completion_tokens": 1200, "finish_reason": "length",
             "semantic_completeness_passed": True, "forbidden_content": [],
             "state": "TRUNCATED_TOO_LONG"},
            {"version": 3, "completion_tokens": 1210, "finish_reason": "stop",
             "semantic_completeness_passed": False, "forbidden_content": [],
             "state": "INVALID_CONTENT"},
        ]
        selected = select_material_fallback(records, 1200, 1080, 1320)
        self.assertEqual(selected["version"], 1)

    def test_duplicate_request_signature_detection_is_deterministic(self) -> None:
        records = [
            {"prompt_hash": "same", "request_max_tokens": 8192,
             "source_material_version": None, "operation": "recovery_render"},
            {"prompt_hash": "same", "request_max_tokens": 8192,
             "source_material_version": None, "operation": "recovery_render"},
        ]
        self.assertTrue(duplicate_material_request(
            records, prompt_hash="same", max_output_tokens=8192,
            source_material_version=None, operation="recovery_render",
        ))
        self.assertFalse(duplicate_material_request(
            records, prompt_hash="different", max_output_tokens=8192,
            source_material_version=None, operation="recovery_render",
        ))

    def test_total_gg_call_limit_is_two_blueprints_plus_three_materials(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item("invalid json", 20)
            ],
            key("general_guidance_blueprint_repair", PROBLEM_ID, "blueprint_repair"): [
                item(json.dumps(blueprint()), 140)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item(guidance("LONG"), 1800)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "material_compress_1"): [
                item(guidance("SHORT"), 700)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "material_compress_2"): [
                item(guidance("STILL LONG"), 1500)
            ],
        })
        result = runner._matched_guidance(
            self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
        )
        self.assertFalse(result["metrics"]["token_match_passed"])
        self.assertTrue(result["metrics"]["fallback_candidate_used"])
        self.assertEqual(len(model.calls), 5)
        self.assertEqual(
            [call["max_output_tokens"] for call in model.calls],
            [2048, 2048, 8192, 8192, 8192],
        )

    def test_all_semantically_invalid_material_has_no_fallback(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item(json.dumps(blueprint()), 140)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item("generic advice", 1000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "material_repair_1"): [
                item("still generic", 1000)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "material_repair_2"): [
                item("again generic", 1000)
            ],
            key("general_guidance_adjust", PROBLEM_ID,
                "material_deduplicated_recovery_2"): [
                item("again generic", 1000)
            ],
        })
        with self.assertRaises(GGContentValidationError):
            runner._matched_guidance(
                self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
            )
        match = json.loads(
            (self.root / "problem/teaching_materials/general_guidance/match.json")
            .read_text(encoding="utf-8")
        )
        self.assertIsNone(match["fallback_version"])
        self.assertIsNone(match["selected_version"])
        self.assertEqual(match["invalid_versions"], [0, 1, 2])
        self.assertEqual(len(model.calls), 4)

    def test_new_policy_resume_reuses_blueprint_and_material(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item(json.dumps(blueprint()), 140)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item(guidance(), 1000)
            ],
        })
        problem_dir = self.root / "problem"
        first = runner._matched_guidance(problem_dir, PROBLEM_ID, PUBLIC_PROBLEM, 1000)
        calls = len(model.calls)
        resumed = PilotRunner(
            runner.config, model, judge=NoJudge(), project_root=ROOT
        )
        second = resumed._matched_guidance(problem_dir, PROBLEM_ID, PUBLIC_PROBLEM, 1000)
        self.assertEqual(len(model.calls), calls)
        self.assertEqual(first["metrics"], second["metrics"])

    def test_all_gg_prompts_exclude_external_sentinels(self) -> None:
        key = MockModelClient.key
        runner, model = self.runner({
            key("general_guidance_blueprint", PROBLEM_ID, "blueprint_initial"): [
                item(json.dumps(blueprint()), 140)
            ],
            key("general_guidance", PROBLEM_ID, "material_initial"): [
                item(guidance("LONG"), 1800)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "material_compress_1"): [
                item(guidance("MATCH"), 1000)
            ],
        })
        runner._matched_guidance(
            self.root / "problem", PROBLEM_ID, PUBLIC_PROBLEM, 1000
        )
        forbidden = (
            "TEACHER_PLANNING_SENTINEL", "TEACHER_FINAL_SENTINEL",
            "TEACHER_CODE_SENTINEL", "VERDICT_SENTINEL", "FF_CONTENT_SENTINEL",
            "HIDDEN_TEST_SENTINEL", "JUDGE_SENTINEL", "ORACLE_SENTINEL",
        )
        for call in model.calls:
            visible = call["system_prompt"] + "\n" + call["user_prompt"]
            self.assertFalse(any(value in visible for value in forbidden))


if __name__ == "__main__":
    unittest.main()
