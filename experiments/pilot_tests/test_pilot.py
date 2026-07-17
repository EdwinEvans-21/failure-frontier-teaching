from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
import subprocess
import sys
from difflib import unified_diff

from ffjudge.models import JudgeResult, Verdict

from experiments.pilot.code_extraction import extract_single_python_code
from experiments.pilot.config import load_config
from experiments.pilot.model_client import MockModelClient
from experiments.pilot.orchestrator import (
    PilotRunner,
    build_summary,
    coarse_verdict,
    token_relative_error,
)


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "experiments" / "configs" / "pilot_v1.yaml"
PROBLEM_ID = "lc-0009-palindrome-number"


def solver_response(marker: str) -> str:
    return (
        "## Approach\nDeterministic mock.\n\n## Code\n```python\n"
        f"# {marker}\nclass Solution:\n    pass\n```"
    )


class FakeJudge:
    def __init__(self) -> None:
        self.calls = 0

    def judge(self, submission, problem, tests, *, phase):
        self.calls += 1
        source = Path(submission).read_text(encoding="utf-8")
        verdict = Verdict.ACCEPTED if "AC_MARKER" in source else Verdict.WRONG_ANSWER
        return JudgeResult(verdict, phase, 0, 1, 7, "internal-only")


class FlakyJudge(FakeJudge):
    def judge(self, submission, problem, tests, *, phase):
        self.calls += 1
        if self.calls == 1:
            return JudgeResult(Verdict.INTERNAL_ERROR, phase, 0, 1, 0, "internal")
        return JudgeResult(Verdict.ACCEPTED, phase, 1, 1, 5, "")


class PilotCodeExtractionTests(unittest.TestCase):
    def test_extracts_exactly_one_python_block(self):
        result = extract_single_python_code(solver_response("OK"))
        self.assertTrue(result.ok)
        self.assertIn("class Solution", result.code or "")

    def test_rejects_missing_multiple_ambiguous_and_truncated_blocks(self):
        self.assertEqual(
            extract_single_python_code("no code").error,
            "missing_python_code_block",
        )
        multiple = "```python\na=1\n```\n```python\nb=2\n```"
        self.assertEqual(
            extract_single_python_code(multiple).error,
            "multiple_python_code_blocks",
        )
        ambiguous = "```python\na=1\n```\n```text\nextra\n```"
        self.assertEqual(
            extract_single_python_code(ambiguous).error,
            "ambiguous_code_blocks",
        )
        self.assertEqual(
            extract_single_python_code(solver_response("X"), truncated=True).error,
            "response_truncated",
        )


class PilotConfigurationTests(unittest.TestCase):
    def test_five_problem_config_uses_one_non_reasoning_model_policy(self):
        config = load_config(CONFIG)
        self.assertEqual(len(config.problems), 5)
        self.assertEqual(config.baseline_id, "failure-frontier-baseline-v2")
        self.assertEqual(
            config.baseline_manifest,
            "experiments/baseline_v2/baseline_manifest.json",
        )
        self.assertFalse(config.model.reasoning_mode)
        self.assertEqual(config.execution.judge_phase, "hidden")
        self.assertEqual(config.teaching_material.token_match_tolerance, 0.05)
        snapshot = json.dumps(config.public_snapshot())
        self.assertNotIn("api_key\"", snapshot)
        self.assertIn("api_key_env", snapshot)

    def test_config_rejects_literal_api_key(self):
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        data["model"]["api_key"] = "secret"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.yaml"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "API keys"):
                load_config(path)

    def test_verdict_mapping_and_token_math_are_coarse(self):
        expected = {
            Verdict.ACCEPTED: "AC",
            Verdict.WRONG_ANSWER: "WA",
            Verdict.SYNTAX_ERROR: "CE",
            Verdict.INVALID_SUBMISSION: "CE",
            Verdict.RUNTIME_ERROR: "RE",
            Verdict.TIME_LIMIT_EXCEEDED: "TLE",
            Verdict.MEMORY_LIMIT_EXCEEDED: "MLE",
            Verdict.INTERNAL_ERROR: "JUDGE_ERROR",
        }
        self.assertEqual({item: coarse_verdict(item) for item in Verdict}, expected)
        self.assertEqual(token_relative_error(100, 105), 0.05)
        self.assertIsNone(token_relative_error(100, None))


class PilotIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def config(self, responses: dict[str, list[dict]], *, mode="mock"):
        script = self.root / "responses.json"
        script.write_text(json.dumps(responses), encoding="utf-8")
        base = load_config(CONFIG)
        return replace(
            base,
            mode=mode,
            problems=(base.problems[0],),
            model=replace(base.model, mock_responses_path=str(script)),
            execution=replace(base.execution, output_root=str(self.root / "runs")),
            prompts_dir=str(ROOT / "experiments" / "prompts"),
            baseline_manifest=str(ROOT / "experiments" / "baseline_v2" / "baseline_manifest.json"),
        )

    @staticmethod
    def item(content, tokens=100):
        return {"content": content, "input_tokens": 50,
                "output_tokens": tokens, "finish_reason": "stop"}

    def failure_responses(self):
        key = MockModelClient.key
        return {
            key("teacher", PROBLEM_ID, "teacher"): [self.item(solver_response("WA_MARKER"))],
            key("failure_frontier", PROBLEM_ID, "failure"): [
                self.item("FAILURE FRONTIER MATERIAL", 100)
            ],
            key("general_guidance", PROBLEM_ID, "initial"): [
                self.item("GENERAL GUIDANCE V0", 130)
            ],
            key("general_guidance_adjust", PROBLEM_ID, "compress_1"): [
                self.item("GENERAL GUIDANCE MATCHED", 103)
            ],
            key("student", PROBLEM_ID, "success_only"): [
                self.item(solver_response("WA_BASELINE"))
            ],
            key("student", PROBLEM_ID, "failure_frontier"): [
                self.item(solver_response("AC_MARKER"))
            ],
            key("student", PROBLEM_ID, "general_guidance"): [
                self.item(solver_response("WA_GG"))
            ],
        }

    def test_failure_branch_token_matching_isolation_artifacts_and_resume(self):
        config = self.config(self.failure_responses())
        model = MockModelClient(config.model)
        judge = FakeJudge()
        runner = PilotRunner(config, model, judge=judge, project_root=ROOT)
        summary = runner.run("failure-run")
        self.assertEqual(summary["teacher_failure_count"], 1)
        self.assertEqual(summary["student_breakthrough_on_teacher_failures"]["failure_frontier"], 1)
        self.assertEqual(summary["baseline_fail_gg_fail_ff_success"], [PROBLEM_ID])
        record = json.loads((self.root / "runs" / "failure-run" / "problems" /
                             PROBLEM_ID / "record.json").read_text(encoding="utf-8"))
        self.assertTrue(record["teaching_material"]["token_match_passed"])
        self.assertEqual(record["teaching_material"]["token_relative_error"], 0.03)
        calls = model.calls
        gg_calls = [call for call in calls if call["role"].startswith("general_guidance")]
        self.assertTrue(gg_calls)
        self.assertTrue(all("FAILURE FRONTIER MATERIAL" not in call["user_prompt"]
                            for call in gg_calls))
        baseline = next(call for call in calls if call["role"] == "student" and
                        call["condition"] == "success_only")
        self.assertNotIn("Additional Material", baseline["user_prompt"])
        ff_student = next(call for call in calls if call["role"] == "student" and
                          call["condition"] == "failure_frontier")
        gg_student = next(call for call in calls if call["role"] == "student" and
                          call["condition"] == "general_guidance")
        self.assertIn("FAILURE FRONTIER MATERIAL", ff_student["user_prompt"])
        self.assertNotIn("GENERAL GUIDANCE", ff_student["user_prompt"])
        self.assertIn("GENERAL GUIDANCE MATCHED", gg_student["user_prompt"])
        self.assertEqual(ff_student["system_prompt"], gg_student["system_prompt"])
        normalized_ff = ff_student["user_prompt"].replace(
            "FAILURE FRONTIER MATERIAL", "<MATERIAL>")
        normalized_gg = gg_student["user_prompt"].replace(
            "GENERAL GUIDANCE MATCHED", "<MATERIAL>")
        self.assertEqual(normalized_ff, normalized_gg)
        call_count, judge_count = len(model.calls), judge.calls
        second = PilotRunner(config, model, judge=judge, project_root=ROOT)
        self.assertEqual(second.run("failure-run"), summary)
        self.assertEqual(len(model.calls), call_count)
        self.assertEqual(judge.calls, judge_count)

    def test_ff_and_gg_student_framing_differs_only_in_material_body(self):
        config = self.config({})
        runner = PilotRunner(config, MockModelClient(config.model),
                             judge=FakeJudge(), project_root=ROOT)
        formatted_problem = "FORMATTED_PROBLEM_SENTINEL"
        ff = runner._rendered_call(
            "student", PROBLEM_ID, "failure_frontier", formatted_problem,
            additional_material="FF_MATERIAL_SENTINEL", success_branch=False)
        gg = runner._rendered_call(
            "student", PROBLEM_ID, "general_guidance", formatted_problem,
            additional_material="GG_MATERIAL_SENTINEL", success_branch=False)
        baseline = runner._rendered_call(
            "student", PROBLEM_ID, "success_only", formatted_problem,
            additional_material="", success_branch=False)
        self.assertEqual(ff["system_prompt"], gg["system_prompt"])
        self.assertEqual(baseline["user_prompt"], formatted_problem)
        self.assertEqual(
            ff["user_prompt"].replace("FF_MATERIAL_SENTINEL", "<MATERIAL>"),
            gg["user_prompt"].replace("GG_MATERIAL_SENTINEL", "<MATERIAL>"),
        )
        differing = [
            line for line in unified_diff(
                ff["user_prompt"].splitlines(),
                gg["user_prompt"].splitlines(),
                lineterm="",
            )
            if line.startswith(("+", "-")) and
            not line.startswith(("+++", "---"))
        ]
        self.assertEqual(differing, [
            "-FF_MATERIAL_SENTINEL",
            "+GG_MATERIAL_SENTINEL",
        ])

    def test_success_branch_gives_identical_material_to_all_students(self):
        key = MockModelClient.key
        responses = {
            key("teacher", PROBLEM_ID, "teacher"): [self.item(solver_response("AC_MARKER"))],
            key("success_teaching", PROBLEM_ID, "success"): [self.item("SUCCESS NOTE")],
        }
        for condition in ("success_only", "failure_frontier", "general_guidance"):
            responses[key("student", PROBLEM_ID, condition)] = [
                self.item(solver_response("AC_MARKER"))
            ]
        config = self.config(responses)
        model = MockModelClient(config.model)
        summary = PilotRunner(config, model, judge=FakeJudge(), project_root=ROOT).run("success-run")
        self.assertEqual(summary["teacher_ac_count"], 1)
        students = [call for call in model.calls if call["role"] == "student"]
        self.assertEqual(len(students), 3)
        self.assertEqual(len({call["system_prompt"] for call in students}), 1)
        self.assertEqual(len({call["user_prompt"] for call in students}), 1)
        self.assertIn("SUCCESS NOTE", students[0]["user_prompt"])

    def test_dry_run_accesses_neither_model_nor_judge(self):
        config = self.config({}, mode="dry-run")
        judge = FakeJudge()
        result = PilotRunner(config, None, judge=judge, project_root=ROOT).run("dry-run")
        self.assertFalse(result["api_accessed"])
        self.assertFalse(result["judge_accessed"])
        self.assertEqual(judge.calls, 0)
        self.assertEqual(len(result["model_calls"]), 7)

    def test_summary_marks_invalid_infrastructure_separately(self):
        records = [{
            "problem_id": "p",
            "teacher": {"verdict": "JUDGE_ERROR", "truncated": False},
            "students": {},
            "teaching_material": {},
            "valid_episode": False,
        }]
        summary = build_summary("r", records)
        self.assertEqual(summary["invalid_episode_count"], 1)
        self.assertEqual(summary["teacher_failure_count"], 0)

    def test_infrastructure_resume_reuses_model_response_and_retries_judge(self):
        key = MockModelClient.key
        responses = {
            key("teacher", PROBLEM_ID, "teacher"): [self.item(solver_response("AC_MARKER"))],
            key("success_teaching", PROBLEM_ID, "success"): [self.item("SUCCESS")],
        }
        for condition in ("success_only", "failure_frontier", "general_guidance"):
            responses[key("student", PROBLEM_ID, condition)] = [
                self.item(solver_response("AC_MARKER"))
            ]
        config = self.config(responses)
        model = MockModelClient(config.model)
        judge = FlakyJudge()
        first = PilotRunner(config, model, judge=judge, project_root=ROOT).run("retry-run")
        self.assertEqual(first["invalid_episode_count"], 1)
        self.assertEqual(len(model.calls), 1)
        second = PilotRunner(config, model, judge=judge, project_root=ROOT).run("retry-run")
        self.assertEqual(second["invalid_episode_count"], 0)
        self.assertEqual(len(model.calls), 5)
        teacher_calls = [call for call in model.calls if call["role"] == "teacher"]
        self.assertEqual(len(teacher_calls), 1)

    def test_module_cli_dry_run_uses_no_api(self):
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        data["execution"]["output_root"] = str(self.root / "cli-runs")
        data["prompts_dir"] = str(ROOT / "experiments" / "prompts")
        data["baseline_manifest"] = str(
            ROOT / "experiments" / "baseline_v2" / "baseline_manifest.json")
        config_path = self.root / "cli.yaml"
        config_path.write_text(json.dumps(data), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "experiments.run_pilot", "--config",
             str(config_path), "--mode", "dry-run", "--run-id", "cli-dry"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["api_accessed"])
        self.assertEqual(len(result["model_calls"]), 35)

    def test_single_problem_smoke_is_isolated_from_formal_outputs(self):
        config = self.config({}, mode="smoke-test")
        model = MockModelClient(config.model)
        judge = FakeJudge()
        result = PilotRunner(config, model, judge=judge, project_root=ROOT).run_smoke(
            PROBLEM_ID, self.root / "external", "mock-smoke")
        self.assertTrue(result["passed"])
        self.assertEqual(result["problem_id"], PROBLEM_ID)
        self.assertTrue(result["informal_smoke_test"])
        self.assertFalse(result["formal_pilot_data_generated"])
        self.assertEqual(len([call for call in model.calls if call["role"] == "teacher"]), 1)
        output = Path(result["output_directory"])
        self.assertTrue((output / "version.json").is_file())
        self.assertTrue((output / "smoke_result.json").is_file())
        self.assertFalse((output / "results.jsonl").exists())
        self.assertFalse((output / "summary.json").exists())
        self.assertFalse((output / "summary.md").exists())
        self.assertTrue(all(result["audit"].values()))


if __name__ == "__main__":
    unittest.main()
