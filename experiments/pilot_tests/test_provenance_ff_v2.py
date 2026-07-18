from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import json
import unittest

from ffjudge.models import JudgeResult, ProblemSpec, Verdict

from experiments.pilot.config import load_config
from experiments.pilot.orchestrator import PilotRunner
from experiments.pilot.model_client import MockModelClient, ModelInfrastructureError
from experiments.pilot.provenance_ff import (
    BASELINE_CONDITION, CRITICAL_CONDITION, DIRECT_CONDITION, FLAT_CONDITION,
    DirectFact, EvidenceGroundedInference, FailureFrontierRecord,
    OrganizerHypothesis, SelectedLowConfidenceExcerpt, SourceArtifact,
    classify_information, parse_organizer_record,
    render_flat_failure_payload, render_shared_failure_payload, sha256_text,
    standardized_error_type,
    validate_direct_instruction,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "experiments/configs/provenance_stratified_ff_v2.example.yaml"
EXPANDED_CONFIG = ROOT / "experiments/configs/provenance_stratified_ff_v2_expanded.yaml"


def fixture_bundle():
    code = "class Solution:\n    def solve(self, n):\n        return n"
    planning = SourceArtifact.create(
        "TEACHER_PLANNING", "teacher/planning/content.md",
        "I claimed that a greedy method was sufficient.")
    final = SourceArtifact.create(
        "TEACHER_FINAL_NATURAL_LANGUAGE", "teacher/final/natural.md",
        "I believe the implementation is linear.")
    analysis = SourceArtifact.create(
        "TEACHER_FAILURE_ANALYSIS", "teacher/failure_analysis/content.md",
        "The boundary condition might be wrong.")
    excerpt = SelectedLowConfidenceExcerpt(
        source_type=planning.source_type,
        source_artifact=planning.source_artifact,
        source_sha256=planning.source_sha256,
        exact_source_excerpt="a greedy method was sufficient",
        confidence_note="Teacher-generated and unverified.",
    )
    record = FailureFrontierRecord(
        policy_version="provenance_stratified_ff_v2",
        final_error_type="WRONG_ANSWER",
        code_artifact="teacher/final/extracted_solution.py",
        code_sha256=sha256_text(code),
        planning_artifact=planning.source_artifact,
        failure_analysis_artifact=analysis.source_artifact,
        evidence_grounded_inferences=(EvidenceGroundedInference(
            claim="The method returns its argument.",
            evidence="The exact return statement is `return n`.",
            evidence_sources=("TEACHER_SUBMITTED_CODE",),
            support_status="PROVISIONALLY_SUPPORTED",
            reproducibility_note="Inspect the method body.",
        ),),
        selected_low_confidence_excerpts=(excerpt,),
        organizer_hypotheses=(OrganizerHypothesis(
            hypothesis="The boundary may be relevant.",
            evidence_limitation="The final error type identifies no failing input.",
        ),),
    )
    return code, planning, final, analysis, record


class ClassificationBoundaryTests(unittest.TestCase):
    def test_source_based_fail_closed_classification(self) -> None:
        self.assertEqual(classify_information(
            source="SYSTEM_RECORD", raw_objective=True), "DIRECT_FACT")
        self.assertEqual(classify_information(
            source="FF_ORGANIZER", short_visible_evidence_chain=True),
            "EVIDENCE_GROUNDED_INFERENCE")
        for source in (
            "TEACHER_PLANNING", "TEACHER_FINAL_NATURAL_LANGUAGE",
            "TEACHER_FAILURE_ANALYSIS", "FF_ORGANIZER", "AMBIGUOUS",
        ):
            self.assertEqual(classify_information(source=source),
                             "LOW_CONFIDENCE_HYPOTHESIS")

    def test_required_claim_examples_follow_provenance_not_wording(self) -> None:
        grounded_claims = (
            "The code contains nested loops.",
            "The implementation has O(n^2) worst-case complexity.",
        )
        for claim in grounded_claims:
            with self.subTest(claim=claim):
                self.assertEqual(classify_information(
                    source="FF_ORGANIZER",
                    short_visible_evidence_chain=True),
                    "EVIDENCE_GROUNDED_INFERENCE")
        low_claims = (
            "The O(n^2) complexity caused the TLE.",
            "Teacher claimed it used greedy.",
            "Teacher final approach.",
            "Teacher complexity analysis.",
            "Teacher correctness proof.",
            "Teacher attempted methods.",
            "Teacher failure diagnosis.",
            "FF organizer unsupported causal explanation.",
            "Ambiguous content.",
        )
        for claim in low_claims:
            with self.subTest(claim=claim):
                self.assertEqual(classify_information(
                    source="TEACHER_OR_UNSUPPORTED"),
                    "LOW_CONFIDENCE_HYPOTHESIS")

    def test_direct_fact_registered_raw_kinds(self) -> None:
        DirectFact("FINAL_ERROR_TYPE", "WRONG_ANSWER", "submission")
        DirectFact("TEACHER_SUBMITTED_CODE", "x = 1", "submission.py")
        DirectFact("EXACT_CODE_EXCERPT", "x = 1", "submission.py")
        DirectFact("CODE_SHA256", "a" * 64, "submission.py")

    def test_natural_language_direct_fact_fixtures_fail(self) -> None:
        fixtures = (
            "The code uses dynamic programming.",
            "The implementation contains two nested loops.",
            "The algorithm is inefficient.",
            "The state is not initialized.",
            "The code probably causes a runtime error.",
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                DirectFact("NATURAL_LANGUAGE_ANALYSIS", fixture, "model")

    def test_error_type_mapping_and_internal_error_boundary(self) -> None:
        self.assertEqual(standardized_error_type({"verdict": "WA"}),
                         "WRONG_ANSWER")
        self.assertEqual(standardized_error_type({
            "verdict": "CE", "final_code_extracted": False}),
            "INVALID_SUBMISSION")
        self.assertEqual(standardized_error_type({
            "verdict": "CE", "final_code_extracted": True}), "SYNTAX_ERROR")
        self.assertIsNone(standardized_error_type({"verdict": "JUDGE_ERROR"}))


class ProvenancePayloadTests(unittest.TestCase):
    def test_complete_sources_code_once_and_round_trip(self) -> None:
        code, planning, final, analysis, record = fixture_bundle()
        payload = render_shared_failure_payload(
            final_error_type="WRONG_ANSWER", code=code,
            code_artifact=record.code_artifact, planning=planning,
            final_natural_language=final, failure_analysis=analysis,
            record=record)
        self.assertEqual(payload.count(code), 1)
        for source in (planning, final, analysis):
            self.assertIn(source.content, payload)
            self.assertIn(source.source_sha256, payload)
            self.assertIn(f'type="{source.source_type}"', payload)
        serialized = json.dumps(record.to_dict())
        self.assertNotIn(code, serialized)
        self.assertNotIn(planning.content, serialized)
        self.assertEqual(FailureFrontierRecord.from_dict(
            record.to_dict()).to_dict(), record.to_dict())

    def test_flat_payload_preserves_all_information_without_tiers(self) -> None:
        code, planning, final, analysis, record = fixture_bundle()
        flat = render_flat_failure_payload(
            final_error_type="WRONG_ANSWER", code=code,
            code_artifact=record.code_artifact, planning=planning,
            final_natural_language=final, failure_analysis=analysis,
            record=record)
        self.assertEqual(flat.count(code), 1)
        atoms = [
            "WRONG_ANSWER", code, record.code_artifact, record.code_sha256,
            record.planning_artifact, record.failure_analysis_artifact,
        ]
        for source in (planning, final, analysis):
            atoms.extend((source.source_type, source.source_artifact,
                          source.source_sha256, source.content))
        for item in record.evidence_grounded_inferences:
            atoms.extend((item.claim, item.evidence, item.organizer_source,
                          item.support_status, item.reproducibility_note,
                          *item.evidence_sources))
        for item in record.selected_low_confidence_excerpts:
            atoms.extend((item.source_type, item.source_artifact,
                          item.source_sha256, item.exact_source_excerpt,
                          item.confidence_note))
        for item in record.organizer_hypotheses:
            atoms.extend((item.source_type, item.hypothesis,
                          item.evidence_limitation))
        for atom in atoms:
            self.assertIn(atom, flat)
        for forbidden in (
            "DIRECT_FACT_SOURCE", "LOW_CONFIDENCE_SOURCE",
            "EVIDENCE_GROUNDED_INFERENCE", "LOW_CONFIDENCE_HYPOTHESIS",
            "## 1.", "## 2.", "## 3.",
        ):
            self.assertNotIn(forbidden, flat)

    def test_organizer_requires_verbatim_provenance(self) -> None:
        code, planning, final, analysis, _ = fixture_bundle()
        raw = json.dumps({
            "evidence_grounded_inferences": [],
            "selected_low_confidence_excerpts": [{
                "source_type": planning.source_type,
                "source_artifact": planning.source_artifact,
                "source_sha256": planning.source_sha256,
                "exact_source_excerpt": "a rewritten claim not in source",
                "confidence_note": "unverified",
            }],
            "organizer_hypotheses": [],
        })
        with self.assertRaisesRegex(ValueError, "not verbatim"):
            parse_organizer_record(
                raw, final_error_type="WRONG_ANSWER",
                code_artifact="code.py", code_sha256=sha256_text(code),
                planning_artifact=planning.source_artifact,
                failure_analysis_artifact=analysis.source_artifact,
                sources={s.source_type: s for s in (planning, final, analysis)},
                full_code=code)

    def test_organizer_record_rejects_future_guidance_and_code(self) -> None:
        code, planning, final, analysis, _ = fixture_bundle()
        sources = {s.source_type: s for s in (planning, final, analysis)}
        for forbidden in ("The next algorithm should use the following algorithm.",
                          "```python\npass\n```", "Here is pseudocode"):
            raw = json.dumps({
                "evidence_grounded_inferences": [],
                "selected_low_confidence_excerpts": [],
                "organizer_hypotheses": [{
                    "hypothesis": forbidden,
                    "evidence_limitation": "limited",
                }],
            })
            with self.subTest(forbidden=forbidden), self.assertRaisesRegex(
                    ValueError, "prohibited guidance"):
                parse_organizer_record(
                    raw, final_error_type="WRONG_ANSWER",
                    code_artifact="code.py", code_sha256=sha256_text(code),
                    planning_artifact=planning.source_artifact,
                    failure_analysis_artifact=analysis.source_artifact,
                    sources=sources, full_code=code)

    def test_record_limits(self) -> None:
        _, _, _, _, record = fixture_bundle()
        with self.assertRaisesRegex(ValueError, "at most three"):
            FailureFrontierRecord(**{
                **record.__dict__,
                "organizer_hypotheses": tuple(
                    OrganizerHypothesis(str(i), "limited") for i in range(4))
            })


class PromptIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG)
        self.runner = PilotRunner(self.config, None, judge=object(),
                                  project_root=ROOT)
        self.problem = "PUBLIC_PROBLEM_SENTINEL"
        self.payload = "SHARED_PAYLOAD_SENTINEL"
        self.assertEqual(self.config.teaching_material.gg_acceptance_policy,
                         "semantic_complete_no_length_v2")

    def render(self, condition: str, stage: str = "planning") -> dict[str, str]:
        return self.runner._rendered_solver_call(
            stage, "student", "fixture", condition, self.problem,
            additional_material=self.payload,
            planning_content="PLANNING_SENTINEL",
            planning_status="STATUS_SENTINEL")

    def test_baseline_is_public_problem_only(self) -> None:
        rendered = self.render(BASELINE_CONDITION)
        self.assertEqual(rendered["user_prompt"], self.problem)
        self.assertIn("Verify that your proposed algorithm satisfies",
                      rendered["system_prompt"])
        for forbidden in ("SHARED_PAYLOAD_SENTINEL", "previous", "error type"):
            self.assertNotIn(forbidden, rendered["user_prompt"].lower())

    def test_direct_and_critical_share_payload_and_output_requirements(self) -> None:
        direct = self.render(DIRECT_CONDITION)
        critical = self.render(CRITICAL_CONDITION)
        self.assertEqual(direct["system_prompt"], critical["system_prompt"])
        self.assertEqual(direct["user_prompt"].count(self.payload), 1)
        self.assertEqual(critical["user_prompt"].count(self.payload), 1)
        self.assertEqual(
            direct["user_prompt"].split("# Shared Failure Materials\n\n", 1)[1],
            critical["user_prompt"].split("# Shared Failure Materials\n\n", 1)[1])
        self.assertEqual(self.render(DIRECT_CONDITION, "final")["system_prompt"],
                         self.render(CRITICAL_CONDITION, "final")["system_prompt"])

    def test_flat_uses_exact_direct_prompt_with_separate_material(self) -> None:
        for stage in ("planning", "final"):
            direct = self.render(DIRECT_CONDITION, stage)
            flat = self.render(FLAT_CONDITION, stage)
            self.assertEqual(direct["system_prompt"], flat["system_prompt"])
            self.assertEqual(direct["user_prompt"], flat["user_prompt"])

    def test_direct_is_neutral_and_critical_selective(self) -> None:
        direct = (ROOT / "experiments/prompts/direct_ff_v2.md").read_text()
        critical = (ROOT / "experiments/prompts/critical_ff_v2.md").read_text()
        validate_direct_instruction(direct)
        self.assertNotIn("selectively inherit", direct.lower())
        self.assertIn("selectively inherit", critical.lower())
        self.assertIn("fallible model-generated", critical.lower())
        for fixture in (
            "Think critically about the Teacher materials.",
            "Do not blindly trust the report.", "Verify every claim.",
            "Reclassify the evidence.",
            "Independently reconstruct the solution before using the materials.",
        ):
            with self.assertRaises(ValueError):
                validate_direct_instruction(fixture)
        validate_direct_instruction(
            "Verify that your proposed algorithm satisfies the public constraints. "
            "Check state transitions, boundaries, initialization, and complexity. "
            "Ensure the final code implements your proposed solution.")

    def test_teacher_analysis_and_organizer_boundaries(self) -> None:
        teacher = (ROOT / "experiments/prompts/teacher_failure_analysis_v2.md").read_text()
        organizer = (ROOT / "experiments/prompts/ff_organizer_v2.md").read_text()
        for phrase in ("unverified hypothesis", "Do not propose a next algorithm",
                       "Do not output code or pseudocode", "definitive root cause"):
            self.assertIn(phrase.lower(), teacher.lower())
        self.assertIn("ff organizer", organizer.lower())
        self.assertIn("fallible model-generated", organizer.lower())
        self.assertNotIn("formal verifier", organizer.lower().replace(
            "not a formal, independent, or static verifier", ""))
        for phrase in ("Do not recommend an algorithm", "Do not rewrite a Teacher claim",
                       "Do not claim to know the failure root cause"):
            self.assertIn(phrase.lower(), organizer.lower())

    def test_v2_gg_has_no_length_matching_requirement(self) -> None:
        blueprint = self.runner._rendered_call(
            "general_guidance_blueprint", "fixture", "blueprint_initial",
            self.problem, target_tokens=1000, lower_bound=900, upper_bound=1100)
        material = self.runner._rendered_call(
            "general_guidance", "fixture", "material_initial", self.problem,
            direction="material", blueprint="{}", target_tokens=1000,
            lower_bound=900, upper_bound=1100, section_budget="{}",
            paragraph_budget="{}", revision_index=0)
        visible = blueprint["system_prompt"] + material["system_prompt"]
        self.assertNotIn("write between", visible.lower())
        self.assertNotIn("targeting 1000", visible.lower())
        self.assertNotIn("900", visible)
        self.assertNotIn("1100", visible)
        self.assertIn("no required token target", visible.lower())
        self.assertIn("four substantive semantic regions", visible.lower())
        self.assertIn("do not include code or pseudocode", visible.lower())

    def test_expanded_smoke_config_freezes_all_five_conditions(self) -> None:
        config = load_config(EXPANDED_CONFIG)
        self.assertEqual(len(config.problems), 31)
        self.assertEqual(config.student_conditions, (
            BASELINE_CONDITION, DIRECT_CONDITION, CRITICAL_CONDITION,
            FLAT_CONDITION, "general_guidance"))
        self.assertEqual(config.mode, "smoke-test")
        self.assertEqual(config.baseline_id,
                         "failure-frontier-baseline-v3-expanded")

    def test_legacy_prompt_hashes_unchanged(self) -> None:
        expected = {
            "failure_frontier.md": "cd7c0417304e1918e0d7e6dc7399a20163d8382ecda7908f90d08cb4abc453b9",
            "failure_frontier_user.md": "d6b987ccc60f7045a8315bd178b3df227a2f559791782af4e96fac0c7c3fc118",
            "student_user_with_material.md": "2a2c5d10efac68b1ab742ee43bc519a783ca4a8caf974452b7ff74f3f703dc05",
            "student_user_with_critical_ff.md": "0c701c74810a379f36fc709de9d14baa7b723503e02c2e23759b05ef10268008",
            "solver_planning.md": "fd1c48daa284aeb7251827bdc9a479b22bfe1d1f4252fae8c9b2e3e2fb574bca",
            "solver_final.md": "6c0aa3cf4c0aa914176bfd5e4b0ba994512aa43b14082df6e0fd1f772adf5271",
        }
        for name, digest in expected.items():
            self.assertEqual(sha256_text((ROOT / "experiments/prompts" / name).read_text()),
                             digest)

    def test_dry_run_has_no_api_or_judge_and_declares_v2(self) -> None:
        with TemporaryDirectory() as temporary:
            self.runner.run_dir = Path(temporary)
            plan = self.runner._dry_run("fixture")
        self.assertFalse(plan["api_accessed"])
        self.assertFalse(plan["judge_accessed"])
        self.assertTrue(plan["direct_critical_payload_byte_equal"])
        self.assertTrue(plan["direct_critical_final_static_equal"])
        self.assertTrue(plan["direct_flat_prompt_template_equal"])
        self.assertEqual(plan["student_treatment_policies"]["flat"],
                         "flat_ff_v2")
        roles = {call["role"] for call in plan["model_calls"]}
        self.assertIn("teacher_failure_analysis_v2", roles)
        self.assertIn("ff_organizer_v2", roles)

    def test_checked_prompt_audit_and_treatment_manifest(self) -> None:
        audit_root = ROOT / "prompt_audits/provenance_stratified_ff_v2"
        summary = json.loads((audit_root / "audit_summary.json").read_text())
        manifest = json.loads((audit_root / "treatment_manifest.json").read_text())
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["representative_fixture_count"], 7)
        self.assertFalse(summary["real_api_accessed"])
        self.assertFalse(summary["judge_accessed"])
        self.assertEqual(summary["gg_acceptance_policy"],
                         "semantic_complete_no_length_v2")
        self.assertFalse(summary["gg_token_match_required"])
        self.assertEqual(manifest["failure_frontier_policy"],
                         "provenance_stratified_ff_v2")
        self.assertEqual(manifest["treatment_differences"]["direct_vs_critical"],
                         "source-aware selective inheritance instruction")
        self.assertEqual(manifest["treatment_differences"]["direct_vs_flat"],
                         "provenance-tier presentation only")
        self.assertTrue(summary["flat_uses_direct_prompt_all"])
        self.assertTrue(summary["flat_has_no_confidence_tier_markers_all"])
        self.assertEqual(manifest["gg_acceptance_policy"],
                         "semantic_complete_no_length_v2")
        self.assertFalse(manifest["gg_token_match_required"])
        for problem_id in (
            "lc-1786-number-of-restricted-paths-from-first-to-last-node",
            "lc-1851-minimum-interval-to-include-each-query",
            "lc-2809-minimum-time-to-make-array-sum-at-most-x",
            "lc-2940-find-building-where-alice-and-bob-can-meet",
            "lc-2945-find-maximum-non-decreasing-array-length",
            "lc-3022-minimize-or-of-remaining-elements-using-operations",
            "lc-3077-maximum-strength-of-k-disjoint-subarrays",
        ):
            leakage = json.loads((audit_root / problem_id /
                                  "leakage_audit.json").read_text())
            classification = json.loads((audit_root / problem_id /
                                         "classification_audit.json").read_text())
            self.assertTrue(all(leakage.values()))
            self.assertTrue(all(classification.values()))


class V2RunnerBoundaryTests(unittest.TestCase):
    @staticmethod
    def _judge(verdict: Verdict):
        class Judge:
            def __init__(self) -> None:
                self.calls = 0

            def judge(self, submission, problem, tests, *, phase):
                self.calls += 1
                return JudgeResult(verdict, phase, 0, 1, 1, "internal-only")
        return Judge()

    def configured(self, root: Path, responses: dict[str, list[dict]]):
        script = root / "responses.json"
        script.write_text(json.dumps(responses), encoding="utf-8")
        base = load_config(CONFIG)
        return replace(
            base, mode="mock", problems=(base.problems[0],),
            model=replace(base.model, mock_responses_path=str(script)),
            execution=replace(base.execution, output_root=str(root / "runs")),
            prompts_dir=str(ROOT / "experiments/prompts"),
            baseline_manifest=str(
                ROOT / "experiments/baseline_v3/baseline_manifest.json"),
        )

    def test_v2_failure_material_resume_reuses_all_completed_calls(self) -> None:
        key = MockModelClient.key
        organizer = json.dumps({
            "evidence_grounded_inferences": [],
            "selected_low_confidence_excerpts": [],
            "organizer_hypotheses": [],
        })
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.configured(root, {
                key("ff_organizer_v2", "lc-0009-palindrome-number", "failure"): [{
                    "content": organizer, "input_tokens": 20,
                    "output_tokens": 100, "finish_reason": "stop"}],
            })
            model = MockModelClient(config.model)
            judge = self._judge(Verdict.WRONG_ANSWER)
            runner = PilotRunner(config, model, judge=judge, project_root=ROOT)
            runner.run_dir = root / "run"
            first = runner._run_problem("resume-v2", config.problems[0])
            call_count = len(model.calls)
            judge_count = judge.calls
            second = runner._run_problem("resume-v2", config.problems[0])
            self.assertEqual(first, second)
            self.assertEqual(len(model.calls), call_count)
            self.assertEqual(judge.calls, judge_count)
            provenance = first["provenance_failure_frontier"]
            self.assertTrue(provenance["direct_critical_payload_byte_equal"])
            self.assertTrue(provenance["flat_payload_uses_same_information"])
            self.assertTrue(provenance["flat_uses_direct_instruction"])
            self.assertNotEqual(provenance["shared_payload_sha256"],
                                provenance["flat_payload_sha256"])
            self.assertEqual(provenance["gg_acceptance_policy"],
                             "semantic_complete_no_length_v2")
            self.assertTrue(first["condition_comparison_eligible"])
            material = first["teaching_material"]
            self.assertFalse(material["token_match_required"])
            self.assertIsNone(material["token_match_passed"])
            self.assertIsNone(material["lower_bound"])
            self.assertIsNone(material["upper_bound"])
            self.assertEqual(material["selection_experiment_tier"],
                             "formal_semantic_complete")
            self.assertEqual(material["selected_version"], 0)
            self.assertEqual(sum(call["role"] == "general_guidance"
                                 for call in model.calls), 1)
            self.assertEqual(sum(call["role"] == "general_guidance_adjust"
                                 for call in model.calls), 0)
            manifest = json.loads((
                runner.run_dir / "problems/lc-0009-palindrome-number/"
                "teaching_materials/provenance_ff_v2/source_manifest.json"
            ).read_text())
            self.assertEqual(manifest["shared_payload_sha256"],
                             provenance["shared_payload_sha256"])
            self.assertEqual(sum(call["role"] == "teacher_failure_analysis_v2"
                                 for call in model.calls), 1)
            self.assertEqual(sum(call["role"] == "ff_organizer_v2"
                                 for call in model.calls), 1)
            smoke_audit = runner._smoke_audit(first, config.problems[0])
            self.assertTrue(all(smoke_audit.values()), smoke_audit)
            payload_path = (
                runner.run_dir / "problems/lc-0009-palindrome-number/"
                "teaching_materials/provenance_ff_v2/shared_failure_payload.txt")
            payload_path.write_text(payload_path.read_text() + "tamper")
            with self.assertRaisesRegex(ModelInfrastructureError,
                                        "shared payload hash"):
                runner._run_problem("resume-v2", config.problems[0])

    def test_internal_error_stops_before_v2_material_and_students(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.configured(root, {})
            model = MockModelClient(config.model)
            judge = self._judge(Verdict.INTERNAL_ERROR)
            runner = PilotRunner(config, model, judge=judge, project_root=ROOT)
            runner.run_dir = root / "run"
            record = runner._run_problem("internal-v2", config.problems[0])
            self.assertFalse(record["valid_episode"])
            self.assertEqual(record["infrastructure_error"], "judge")
            self.assertEqual(record["students"], {})
            self.assertFalse(record["condition_comparison_eligible"])
            roles = {call["role"] for call in model.calls}
            self.assertNotIn("teacher_failure_analysis_v2", roles)
            self.assertNotIn("ff_organizer_v2", roles)


if __name__ == "__main__":
    unittest.main()
