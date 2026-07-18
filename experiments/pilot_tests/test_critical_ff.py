from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest

from experiments.pilot.config import load_config
from experiments.pilot.model_client import MockModelClient
from experiments.pilot.orchestrator import PilotRunner, build_summary
from experiments.pilot_tests.test_pilot import (
    CONFIG,
    PROBLEM_ID,
    ROOT,
    FakeJudge,
    final_response,
    guidance_response,
)


CRITICAL = "critical_failure_frontier"
CRITICAL_CONFIG = (
    ROOT / "experiments" / "configs" / "expanded_critical_ff_v1.yaml"
)
CONDITIONS = (
    "success_only",
    "failure_frontier",
    CRITICAL,
    "general_guidance",
)


class CriticalFailureFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def item(content: str, tokens: int = 100) -> dict:
        return {
            "content": content,
            "input_tokens": 50,
            "output_tokens": tokens,
            "finish_reason": "stop",
        }

    def config(self, responses: dict[str, list[dict]], *, mode: str = "mock"):
        path = self.root / "responses.json"
        path.write_text(json.dumps(responses), encoding="utf-8")
        base = load_config(CONFIG)
        return replace(
            base,
            mode=mode,
            student_conditions=CONDITIONS,
            problems=(base.problems[0],),
            model=replace(base.model, mock_responses_path=str(path)),
            execution=replace(base.execution, output_root=str(self.root / "runs")),
            prompts_dir=str(ROOT / "experiments" / "prompts"),
            baseline_manifest=str(
                ROOT / "experiments" / "baseline_v3" / "baseline_manifest.json"
            ),
        )

    def failure_responses(self) -> dict[str, list[dict]]:
        key = MockModelClient.key
        return {
            key("teacher", PROBLEM_ID, "teacher"): [
                self.item(final_response("WA_TEACHER"))
            ],
            key("failure_frontier", PROBLEM_ID, "failure"): [
                self.item("SAME_FF_MATERIAL_SENTINEL", 100)
            ],
            key("general_guidance", PROBLEM_ID, "initial"): [
                self.item(guidance_response("GG_LONG"), 130)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                self.item(guidance_response("GG_MATCHED"), 103)
            ],
            key("student", PROBLEM_ID, "success_only"): [
                self.item(final_response("WA_BASELINE"))
            ],
            key("student", PROBLEM_ID, "failure_frontier"): [
                self.item(final_response("WA_NAIVE"))
            ],
            key("student", PROBLEM_ID, CRITICAL): [
                self.item(final_response("AC_MARKER"))
            ],
            key("student", PROBLEM_ID, "general_guidance"): [
                self.item(final_response("WA_GG"))
            ],
        }

    def test_default_config_preserves_naive_three_condition_protocol(self) -> None:
        self.assertEqual(load_config(CONFIG).student_conditions, (
            "success_only", "failure_frontier", "general_guidance"
        ))

    def test_expanded_critical_config_is_explicitly_opt_in(self) -> None:
        config = load_config(CRITICAL_CONFIG)
        self.assertEqual(config.student_conditions, CONDITIONS)
        self.assertEqual(len(config.problems), 31)
        self.assertEqual(
            config.baseline_id, "failure-frontier-baseline-v3-expanded"
        )
        self.assertEqual(Path(config.source_path), CRITICAL_CONFIG.resolve())

    def test_smoke_metadata_hashes_the_actual_critical_config(self) -> None:
        config = load_config(CRITICAL_CONFIG)
        runner = PilotRunner(config, None, judge=FakeJudge(), project_root=ROOT)
        metadata = runner._smoke_metadata(
            "lc-3077-maximum-strength-of-k-disjoint-subarrays"
        )
        self.assertEqual(Path(metadata["config_path"]), CRITICAL_CONFIG.resolve())
        import hashlib
        self.assertEqual(
            metadata["config_sha256"],
            hashlib.sha256(CRITICAL_CONFIG.read_bytes()).hexdigest(),
        )

    def test_critical_and_naive_share_material_and_solver_limits(self) -> None:
        config = self.config({})
        runner = PilotRunner(config, None, judge=FakeJudge(), project_root=ROOT)
        values = {
            "problem_id": PROBLEM_ID,
            "problem": "FORMATTED_PROBLEM",
            "additional_material": "SAME_FF_MATERIAL_SENTINEL",
            "success_branch": False,
        }
        naive = runner._rendered_solver_call(
            "planning", "student", condition="failure_frontier", **values
        )
        critical = runner._rendered_solver_call(
            "planning", "student", condition=CRITICAL, **values
        )
        self.assertEqual(naive["system_prompt"], critical["system_prompt"])
        self.assertTrue(naive["user_prompt"].endswith("SAME_FF_MATERIAL_SENTINEL\n"))
        self.assertTrue(critical["user_prompt"].endswith("SAME_FF_MATERIAL_SENTINEL\n"))
        critical_marker = "Do not accept the Additional Material as a correction key"
        self.assertNotIn(critical_marker, naive["user_prompt"])
        self.assertIn(critical_marker, critical["user_prompt"])
        self.assertIn("coarse verdict alone does not prove", critical["user_prompt"])
        for received_information in (
            "title and statement",
            "input contract",
            "output contract",
            "entrypoint",
            "public constraints",
            "public time and memory limits",
            "public examples",
            "shared stage instructions",
            "your own Planning response",
            "descriptions or quotations of the earlier approach",
            "proposed failure causes",
            "formulas, reductions, invariants",
        ):
            self.assertIn(received_information, critical["user_prompt"])
        self.assertIn(
            "every proposed replacement algorithm", critical["user_prompt"]
        )
        self.assertIn("symbolic consistency check", critical["user_prompt"])
        self.assertIn("`keep`, `revise`, or `reject`", critical["user_prompt"])
        naive_final = runner._rendered_solver_call(
            "final", "student", condition="failure_frontier",
            planning_content="PLAN", planning_status="complete", **values
        )
        critical_final = runner._rendered_solver_call(
            "final", "student", condition=CRITICAL,
            planning_content="PLAN", planning_status="complete", **values
        )
        self.assertEqual(naive_final["system_prompt"], critical_final["system_prompt"])

    def test_success_branch_keeps_all_student_prompts_identical(self) -> None:
        config = self.config({})
        runner = PilotRunner(config, None, judge=FakeJudge(), project_root=ROOT)
        prompts = [
            runner._rendered_solver_call(
                "planning", "student", PROBLEM_ID, condition,
                "FORMATTED_PROBLEM", additional_material="SUCCESS_MATERIAL",
                success_branch=True,
            )["user_prompt"]
            for condition in CONDITIONS
        ]
        self.assertEqual(len(set(prompts)), 1)

    def test_mock_chain_records_paired_material_and_outcome(self) -> None:
        config = self.config(self.failure_responses())
        model = MockModelClient(config.model)
        judge = FakeJudge()
        summary = PilotRunner(
            config, model, judge=judge, project_root=ROOT
        ).run("critical-pair")
        comparison = summary["naive_vs_critical_failure_frontier"]
        self.assertEqual(comparison["paired_episode_count"], 1)
        self.assertEqual(comparison["critical_only_ac"], [PROBLEM_ID])
        self.assertEqual(comparison["verdict_transitions"], {"WA->AC": 1})
        record = json.loads((
            self.root / "runs" / "critical-pair" / "problems" /
            PROBLEM_ID / "record.json"
        ).read_text(encoding="utf-8"))
        self.assertTrue(record["critical_ff_pair"]["material_identical"])
        self.assertEqual(
            record["critical_ff_pair"]["naive_material_sha256"],
            record["critical_ff_pair"]["critical_material_sha256"],
        )
        self.assertEqual(set(record["student_execution_order"]), set(CONDITIONS))
        self.assertEqual(judge.calls, 5)
        calls = [call for call in model.calls if call["role"] == "student_planning"]
        naive = next(c for c in calls if c["condition"] == "failure_frontier")
        critical = next(c for c in calls if c["condition"] == CRITICAL)
        self.assertIn("SAME_FF_MATERIAL_SENTINEL", naive["user_prompt"])
        self.assertIn("SAME_FF_MATERIAL_SENTINEL", critical["user_prompt"])
        marker = "Do not accept the Additional Material as a correction key"
        self.assertNotIn(marker, naive["user_prompt"])
        self.assertIn(marker, critical["user_prompt"])

        record["critical_ff_pair"]["critical_material_sha256"] = "tampered"
        tampered = build_summary("tampered", [record])
        self.assertEqual(
            tampered["naive_vs_critical_failure_frontier"]["paired_episode_count"],
            0,
        )

    def test_opt_in_dry_run_counts_and_order(self) -> None:
        config = self.config({}, mode="dry-run")
        runner = PilotRunner(config, None, judge=FakeJudge(), project_root=ROOT)
        result = runner.run("critical-dry")
        self.assertEqual(len(result["model_calls"]), 17)
        self.assertEqual(result["minimum_model_calls_if_all_teacher_success"], 11)
        self.assertEqual(result["maximum_model_calls_under_configured_gg_attempts"], 16)
        self.assertEqual(result["expected_judge_submissions"], 5)
        self.assertEqual(
            set(result["student_execution_orders"][PROBLEM_ID]), set(CONDITIONS)
        )

    def test_expanded_order_can_represent_all_four_condition_permutations(self) -> None:
        config = replace(
            self.config({}),
            baseline_id="failure-frontier-baseline-v3-expanded",
        )
        runner = PilotRunner(config, None, judge=FakeJudge(), project_root=ROOT)
        orders = {
            runner._student_order("critical-expanded", f"problem-{index}")
            for index in range(1000)
        }
        self.assertEqual(len(orders), 24)
        self.assertTrue(all(set(order) == set(CONDITIONS) for order in orders))


if __name__ == "__main__":
    unittest.main()
