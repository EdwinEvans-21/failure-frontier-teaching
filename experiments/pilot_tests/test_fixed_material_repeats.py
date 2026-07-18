from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest


ROOT = Path(__file__).parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.fixed_material.runner import (  # noqa: E402
    FixedMaterialRunner,
    fixed_material_cell_eligibility,
)
from experiments.fixed_material.schedule import (  # noqa: E402
    CONDITIONS,
    PROBLEM_IDS,
    build_schedule,
)
from experiments.fixed_material.source import (  # noqa: E402
    _eligible,
    verify_fixed_material_snapshot,
)
from experiments.pilot.code_extraction import extract_fenced_python_submission  # noqa: E402
from experiments.pilot.prompts import PromptRenderer  # noqa: E402
from experiments.pilot.model_client import MockModelClient  # noqa: E402
from experiments.pilot.config import ModelConfig  # noqa: E402
from ffjudge.models import JudgeResult, Verdict  # noqa: E402


SOURCE_RUN = Path(
    r"E:\fft-runs\expanded-exploratory-v1\expanded-exploratory-v1-20260718T044702Z"
)
SNAPSHOT = Path(
    r"E:\fft-runs\fixed-material-sources\expanded-exploratory-v1-fixed-seven"
)


class FixedMaterialSourceTests(unittest.TestCase):
    def test_authoritative_seven_source_rows_are_strictly_eligible(self) -> None:
        if not SOURCE_RUN.is_dir():
            self.skipTest("authoritative external source run is unavailable")
        rows = {
            row["problem_id"]: row
            for row in (
                json.loads(line)
                for line in (SOURCE_RUN / "results.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            )
        }
        self.assertEqual(set(PROBLEM_IDS), set(PROBLEM_IDS) & rows.keys())
        for problem_id in PROBLEM_IDS:
            with self.subTest(problem_id=problem_id):
                self.assertEqual(_eligible(rows[problem_id]), [])

    def test_source_eligibility_fails_closed(self) -> None:
        row = {
            "branch": "teacher_failure",
            "condition_comparison_eligible": True,
            "teaching_material": {
                "token_match_passed": True,
                "fallback_candidate_used": False,
                "failure_frontier_output_limit_reached": False,
            },
        }
        self.assertEqual(_eligible(row), [])
        row["teaching_material"]["fallback_candidate_used"] = True
        self.assertIn("fallback_candidate_used", _eligible(row))

    def test_snapshot_hashes_verify_and_missing_file_fails(self) -> None:
        if not SNAPSHOT.is_dir():
            self.skipTest("external fixed-material snapshot is unavailable")
        self.assertTrue(verify_fixed_material_snapshot(SNAPSHOT, ROOT)["passed"])
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "snapshot"
            import shutil
            import stat
            shutil.copytree(SNAPSHOT, root)
            victim = root / "materials" / PROBLEM_IDS[0] / "failure_frontier.md"
            victim.chmod(stat.S_IWRITE)
            victim.unlink()
            review = verify_fixed_material_snapshot(root, ROOT)
            self.assertFalse(review["passed"])
            self.assertTrue(any(error.startswith("missing:") for error in review["errors"]))


class FixedMaterialScheduleTests(unittest.TestCase):
    def test_schedule_has_280_unique_cells(self) -> None:
        schedule = build_schedule("fixed-material-test")
        self.assertEqual(len(schedule), 280)
        self.assertEqual(len({row["cell_id"] for row in schedule}), 280)
        self.assertEqual(Counter(row["condition"] for row in schedule), {
            condition: 70 for condition in CONDITIONS
        })
        self.assertEqual(Counter(row["problem_id"] for row in schedule), {
            problem_id: 40 for problem_id in PROBLEM_IDS
        })

    def test_condition_positions_are_balanced(self) -> None:
        schedule = build_schedule("fixed-material-test")
        global_counts = defaultdict(Counter)
        local_counts = defaultdict(Counter)
        for row in schedule:
            global_counts[row["condition"]][row["condition_position"]] += 1
            local_counts[(row["problem_id"], row["condition"])][
                row["condition_position"]
            ] += 1
        self.assertTrue(all(max(c.values()) - min(c.values()) <= 1
                            for c in global_counts.values()))
        self.assertTrue(all(max(c.values()) - min(c.values()) <= 1
                            for c in local_counts.values()))

    def test_schedule_is_run_id_deterministic(self) -> None:
        self.assertEqual(build_schedule("same"), build_schedule("same"))
        self.assertNotEqual(build_schedule("same"), build_schedule("different"))


class FixedMaterialPromptIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = PromptRenderer(ROOT / "experiments/prompts")

    def render(self, condition: str, material: str) -> str:
        problem = "PUBLIC_PROBLEM_SENTINEL"
        if condition == "baseline":
            return problem
        template = (
            "student_user_with_critical_ff.md"
            if condition == "critical_ff" else "student_user_with_material.md"
        )
        return self.renderer.render(
            self.renderer.template(template),
            formatted_problem=problem,
            additional_material=material,
        )

    def test_baseline_has_no_material_or_placeholder(self) -> None:
        prompt = self.render("baseline", "")
        self.assertEqual(prompt, "PUBLIC_PROBLEM_SENTINEL")
        self.assertNotIn("Additional Material", prompt)

    def test_conditions_are_isolated(self) -> None:
        baseline = self.render("baseline", "")
        naive = self.render("naive_ff", "FF_SENTINEL")
        critical = self.render("critical_ff", "FF_SENTINEL")
        gg = self.render("general_guidance", "GG_SENTINEL")
        self.assertNotIn("FF_SENTINEL", baseline)
        self.assertNotIn("GG_SENTINEL", baseline)
        self.assertIn("FF_SENTINEL", naive)
        self.assertNotIn("GG_SENTINEL", naive)
        self.assertIn("FF_SENTINEL", critical)
        self.assertNotIn("GG_SENTINEL", critical)
        self.assertIn("GG_SENTINEL", gg)
        self.assertNotIn("FF_SENTINEL", gg)

    def test_naive_and_critical_material_bytes_are_equal(self) -> None:
        if not SNAPSHOT.is_dir():
            self.skipTest("external fixed-material snapshot is unavailable")
        manifest = json.loads((SNAPSHOT / "fixed_material_manifest.json").read_text())
        for problem_id in PROBLEM_IDS:
            material = (SNAPSHOT / "materials" / problem_id /
                        "failure_frontier.md").read_bytes()
            self.assertEqual(
                __import__("hashlib").sha256(material).hexdigest(),
                manifest["materials"][problem_id]["failure_frontier_sha256"],
            )


class FixedMaterialEligibilityTests(unittest.TestCase):
    def test_model_output_failures_remain_valid_samples(self) -> None:
        for failure in ("planning_truncated", "final_truncated", "extraction_failure"):
            with self.subTest(failure=failure):
                eligible, reasons = fixed_material_cell_eligibility(
                    source_episode_strictly_eligible=True,
                    fixed_material_hashes_verified=True,
                    correct_condition_material_used=True,
                    planning_call_completed=True,
                    final_call_completed=True,
                    infrastructure_error=False,
                )
                self.assertTrue(eligible)
                self.assertEqual(reasons, [])

    def test_infrastructure_error_is_ineligible(self) -> None:
        eligible, reasons = fixed_material_cell_eligibility(
            source_episode_strictly_eligible=True,
            fixed_material_hashes_verified=True,
            correct_condition_material_used=True,
            planning_call_completed=True,
            final_call_completed=True,
            infrastructure_error=True,
        )
        self.assertFalse(eligible)
        self.assertEqual(reasons, ["infrastructure_error"])

    def test_missing_fence_is_model_failure(self) -> None:
        result = extract_fenced_python_submission("class Solution:\n    pass\n")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "missing_python_code_block")


class FixedMaterialDryRunTests(unittest.TestCase):
    def test_dry_run_counts_and_no_access(self) -> None:
        if not SNAPSHOT.is_dir():
            self.skipTest("external fixed-material snapshot is unavailable")
        runner = FixedMaterialRunner(
            ROOT / "experiments/configs/fixed_material_repeats_v1.json",
            SNAPSHOT,
            Path(r"E:\fft-runs\fixed-material-test-output"),
            mode="dry-run",
            project_root=ROOT,
            model=object(),
            judge=object(),
        )
        result = runner.dry_run("fixed-material-test")
        self.assertEqual(result["problem_count"], 7)
        self.assertEqual(result["student_episodes"], 280)
        self.assertEqual(result["maximum_api_calls"], 560)
        self.assertEqual(result["maximum_judge_submissions"], 280)
        self.assertFalse(result["api_accessed"])
        self.assertFalse(result["judge_accessed"])

    def test_mock_full_chain_and_resume_are_idempotent(self) -> None:
        if not SNAPSHOT.is_dir():
            self.skipTest("external fixed-material snapshot is unavailable")

        class AcceptingJudge:
            calls = 0

            def judge(self, *_args, **_kwargs):
                self.calls += 1
                return JudgeResult(
                    verdict=Verdict.ACCEPTED, phase="hidden", passed=1,
                    total=1, runtime_ms=1,
                )

        raw = json.loads((ROOT / "experiments/configs/fixed_material_repeats_v1.json").read_text())
        model_config = ModelConfig(**raw["model"])
        model = MockModelClient(model_config)
        judge = AcceptingJudge()
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            runner = FixedMaterialRunner(
                ROOT / "experiments/configs/fixed_material_repeats_v1.json",
                SNAPSHOT, output, mode="mock", project_root=ROOT,
                model=model, judge=judge,
            )
            summary = runner.run("mock-fixed-material")
            self.assertEqual(summary["completed_cells"], 280)
            self.assertEqual(summary["model_calls"], 560)
            self.assertEqual(judge.calls, 280)
            self.assertEqual(len(model.calls), 560)
            summary_again = runner.run("mock-fixed-material", resume=True)
            self.assertEqual(summary_again["completed_cells"], 280)
            self.assertEqual(judge.calls, 280)
            self.assertEqual(len(model.calls), 560)


if __name__ == "__main__":
    unittest.main()
