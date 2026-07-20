from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from experiments.iterative.aggregation import (
    aggregate_run, parse_lineage_manifests, transition_rows,
)
from experiments.iterative.config import (
    COMPARISON_V2_CONDITIONS, CONDITIONS, FLAT_V2_CONDITION,
    FLAT_V2_CONDITIONS, IterativeConfig,
)
from experiments.iterative.fakes import (
    DeterministicFakeJudge, DeterministicFlatPipeline,
    DeterministicStructuredFlatPipeline,
)
from experiments.iterative.flat_addon import (
    LINEAGE_FLAT_ADDON_RENDERER_VERSION, render_lineage_flat_analysis,
)
from experiments.iterative.fresh_runner import (
    FreshTeacherConfig, FreshTeacherLineageRunner,
)
from experiments.iterative.payloads import (
    ParentMaterial, audit_direct_parent_payload,
    audit_structured_parent_sources, render_inherited_payload,
    render_inherited_payload_v2, sha256_text,
)
from experiments.iterative.roots import (
    canonical_hash, file_hash, freeze_root, locate_episode,
)
from experiments.iterative.runner import IterativeRunner, condition_rotation
from experiments.iterative.transport import SanitizedTransportTracker
from experiments.pilot.model_client import ModelInfrastructureError, ModelResponse
from experiments.pilot.provenance_ff import FLAT_PAYLOAD_RENDERER_VERSION
from experiments.pilot.storage import read_json, write_json, write_text


ROOT = Path(__file__).parents[2]
BASE_CONFIG = ROOT / "experiments/configs/provenance_stratified_ff_v2_expanded.yaml"
FIRST_PROBLEM = "lc-3123-find-edges-in-shortest-paths"


class ScriptedOfflineModel:
    accessed_real_api = False

    def __init__(self, finals=None):
        self.calls = []
        self.finals = {key: list(value) for key, value in (finals or {}).items()}

    def complete(self, **request):
        self.calls.append(dict(request))
        role, condition = request["role"], request["condition"]
        if role.endswith("_planning"):
            content = "Use one checked candidate and verify bounds."
        else:
            scripted = self.finals.get(condition, [])
            content = scripted.pop(0) if scripted else "```python\nclass Solution:\n    pass\n```"
        return ModelResponse(
            content=content, input_tokens=11, output_tokens=7,
            finish_reason="stop", request_id=f"offline-{len(self.calls)}",
            seed=None, seed_supported=False, latency_ms=0,
            token_count_source="offline_fixture", response_id=f"r-{len(self.calls)}",
            returned_model="offline-model", reasoning_content=None,
            total_tokens=18, request_id_supported=True,
        )


class FailOnceFinalModel(ScriptedOfflineModel):
    def __init__(self):
        super().__init__()
        self.failed = False

    def complete(self, **request):
        if request["role"].endswith("_final") and not self.failed:
            self.failed = True
            raise ModelInfrastructureError("offline transport interruption")
        return super().complete(**request)


class FailOnceJudge(DeterministicFakeJudge):
    def __init__(self):
        super().__init__(); self.failed = False

    def judge(self, submission, problem, tests, *, phase):
        if not self.failed:
            self.failed = True
            raise OSError("offline sandbox interruption")
        return super().judge(submission, problem, tests, phase=phase)


class TwoPhaseFlatFixture:
    def __init__(self):
        self.generate_calls = 0; self.validate_calls = 0; self.failed = False

    def generate(self, **request):
        self.generate_calls += 1
        return {"flat_payload": "TWO_PHASE_FLAT", "model_calls": 2,
                "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}

    def validate(self, *, raw, **request):
        self.validate_calls += 1
        if not self.failed:
            self.failed = True
            raise ModelInfrastructureError("offline validation interruption")
        return raw


def make_source(root: Path, episode_id="root-episode") -> Path:
    source = root / "source"
    episode = source / "episodes" / episode_id
    problem_dir = episode / "problems" / FIRST_PROBLEM
    config = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    write_json(episode / "config.snapshot.yaml", config)
    code = "class Solution:\n    ROOT_SENTINEL = True\n"
    planning = "ROOT_PLANNING_SENTINEL"
    final = "```python\n" + code + "```"
    flat = "ROOT_FLAT_SENTINEL objective failure notes."
    write_text(problem_dir / "teacher/planning/content.md", planning)
    write_text(problem_dir / "teacher/final/content.md", final)
    write_text(problem_dir / "teacher/final/extracted_solution.py", code)
    write_json(problem_dir / "teacher/judge.internal.json", {"verdict": "WA", "private": "not rendered"})
    provenance = problem_dir / "teaching_materials/provenance_ff_v2"
    ff_record = {"policy_version": "provenance_stratified_ff_v2", "items": []}
    write_json(provenance / "failure_frontier_record.json", ff_record)
    write_text(provenance / "flat_failure_payload.txt", flat)
    flat_hash = hashlib.sha256(flat.encode()).hexdigest()
    write_json(provenance / "source_manifest.json", {
        "flat_payload_sha256": flat_hash,
        "failure_frontier_record_sha256": canonical_hash(ff_record),
    })
    record = {
        "run_id": episode_id, "problem_id": FIRST_PROBLEM, "valid_episode": True,
        "teacher": {"verdict": "WA", "final_code_extracted": True},
        "provenance_failure_frontier": {
            "flat_payload_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
            "flat_payload_sha256": flat_hash,
        },
    }
    write_json(problem_dir / "record.json", record)
    return source


def make_config(temp: Path, source: Path, *, generations=2, repeats=1, mode="mock"):
    return IterativeConfig(
        schema_version="1.0", experiment_policy="minimal_failure_lineage_v1",
        base_pilot_config=str(BASE_CONFIG), source_run_dir=str(source),
        root_episode_ids=("root-episode",), output_root=str(temp / "out"),
        max_generations=generations, lineage_repeats=repeats, stop_on_ac=True,
        condition_order_policy="balanced_rotation_v1", conditions=CONDITIONS,
        mode=mode, source_path=str(temp / "config.yaml"),
    )


def make_v2_source(root: Path, episode_id="root-episode") -> Path:
    source = make_source(root, episode_id)
    problem_dir = source / "episodes" / episode_id / "problems" / FIRST_PROBLEM
    provenance = problem_dir / "teaching_materials/provenance_ff_v2"
    code_path = problem_dir / "teacher/final/extracted_solution.py"
    planning_path = problem_dir / "teacher/planning/content.md"
    planning = "Planning prefix. EXACT_PLANNING_EXCERPT. Planning suffix."
    final_nl_path = provenance / "raw_sources/teacher_final_natural_language.md"
    analysis_path = provenance / "raw_sources/teacher_failure_analysis.md"
    write_text(planning_path, planning)
    write_text(final_nl_path, "Final explanation prefix and suffix.")
    write_text(analysis_path, "Failure analysis prefix and suffix.")
    record = {
        "policy_version": "provenance_stratified_ff_v2",
        "final_error_type": "WRONG_ANSWER",
        "code_artifact": str(code_path),
        "code_sha256": sha256_text(code_path.read_text(encoding="utf-8")),
        "planning_artifact": str(planning_path),
        "failure_analysis_artifact": str(analysis_path),
        "evidence_grounded_inferences": [{
            "claim": "INFERENCE_CLAIM_SENTINEL",
            "evidence": "INFERENCE_EVIDENCE_SENTINEL",
            "evidence_sources": ["PUBLIC_PROBLEM"],
            "support_status": "PROVISIONALLY_SUPPORTED",
            "reproducibility_note": "REPRODUCIBILITY_SENTINEL",
            "organizer_source": "FF_ORGANIZER",
        }],
        "selected_low_confidence_excerpts": [{
            "source_type": "TEACHER_PLANNING",
            "source_artifact": str(planning_path),
            "source_sha256": sha256_text(planning),
            "exact_source_excerpt": "EXACT_PLANNING_EXCERPT",
            "confidence_note": "CONFIDENCE_NOTE_SENTINEL",
        }],
        "organizer_hypotheses": [{
            "hypothesis": "ORGANIZER_HYPOTHESIS_SENTINEL",
            "evidence_limitation": "EVIDENCE_LIMITATION_SENTINEL",
            "source_type": "FF_ORGANIZER_HYPOTHESIS",
        }],
    }
    write_json(provenance / "failure_frontier_record.json", record)
    rejection = {
        "policy": "reject_nonverbatim_excerpt_continue_v1",
        "received_excerpt_count": 2, "accepted_excerpt_count": 1,
        "rejected_excerpt_count": 1,
        "rejected_excerpts": [{"exact_source_excerpt": "REJECTED_SENTINEL"}],
    }
    rejection_path = provenance / "rejected_low_confidence_excerpts.json"
    write_json(rejection_path, rejection)
    manifest = read_json(provenance / "source_manifest.json")
    manifest.update({
        "failure_frontier_record_sha256": canonical_hash(record),
        "rejected_excerpt_audit_artifact": str(rejection_path),
        "rejected_excerpt_audit_sha256": canonical_hash(rejection),
        "source_sha256": {
            "TEACHER_PLANNING": {
                "source_type": "TEACHER_PLANNING",
                "source_artifact": str(planning_path),
                "source_sha256": sha256_text(planning),
            },
            "TEACHER_FINAL_NATURAL_LANGUAGE": {
                "source_type": "TEACHER_FINAL_NATURAL_LANGUAGE",
                "source_artifact": str(final_nl_path),
                "source_sha256": sha256_text(final_nl_path.read_text(encoding="utf-8")),
            },
            "TEACHER_FAILURE_ANALYSIS": {
                "source_type": "TEACHER_FAILURE_ANALYSIS",
                "source_artifact": str(analysis_path),
                "source_sha256": sha256_text(analysis_path.read_text(encoding="utf-8")),
            },
        },
    })
    write_json(provenance / "source_manifest.json", manifest)
    return source


def make_v2_config(temp: Path, source: Path, *, generations=2, mode="mock"):
    return IterativeConfig(
        schema_version="1.0", experiment_policy="minimal_failure_lineage_v1",
        base_pilot_config=str(BASE_CONFIG), source_run_dir=str(source),
        root_episode_ids=("root-episode",), output_root=str(temp / "out-v2"),
        max_generations=generations, lineage_repeats=1, stop_on_ac=True,
        condition_order_policy="balanced_rotation_v1",
        conditions=FLAT_V2_CONDITIONS, mode=mode,
        source_path=str(temp / "config-v2.yaml"),
    )


class PayloadAndRotationTests(unittest.TestCase):
    def test_natural_language_expected_output_phrase_is_not_rejected(self):
        parent = ParentMaterial(
            1, "class Solution:\n    pass", "WA", "code-hash",
            flat_addon=(
                "The model does not know the expected output or hidden test.\n"),
        )
        payload = "Natural language mentions expected output and actual output."
        self.assertEqual(audit_direct_parent_payload(payload, parent, []), [])

    def test_structured_private_judge_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            record = Path(td) / "record.json"
            write_json(record, {
                "policy_version": "provenance_stratified_ff_v2",
                "judge_diagnostics": {
                    "hidden_test_id": 7,
                    "input": "secret",
                    "actual": 2,
                    "expected_value": 3,
                },
            })
            parent = ParentMaterial(
                1, "code", "WA", "hash",
                validated_record_path=str(record),
            )
            issues = audit_structured_parent_sources(parent)
            self.assertIn("private_structured_field:expected_value", issues)
            self.assertIn("private_structured_field:hidden_test_id", issues)
            self.assertIn("private_structured_field:judge_diagnostics", issues)
            self.assertIn("hidden_input_actual_pair", issues)

    def test_structured_model_prose_is_opaque_to_private_data_audit(self):
        with tempfile.TemporaryDirectory() as td:
            record = Path(td) / "record.json"
            write_json(record, {
                "policy_version": "provenance_stratified_ff_v2",
                "organizer_hypotheses": [{
                    "hypothesis": "We do not know the expected output.",
                    "evidence_limitation": "No hidden test was visible.",
                    "source_type": "FF_ORGANIZER_HYPOTHESIS",
                }],
            })
            parent = ParentMaterial(
                1, "code", "WA", "hash",
                validated_record_path=str(record),
            )
            self.assertEqual(audit_structured_parent_sources(parent), [])

    def test_transport_tracker_persists_no_headers_body_or_api_key(self):
        class Response:
            status = 200

        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "attempts.jsonl"
            tracker = SanitizedTransportTracker(artifact)
            tracker.bind({"role": "student_final", "problem_id": "p",
                          "condition": "c"})
            import unittest.mock
            request = unittest.mock.Mock()
            request.get_method.return_value = "POST"
            request.full_url = "https://api.example/chat/completions"
            with unittest.mock.patch("urllib.request.urlopen", return_value=Response()):
                tracker(request, timeout=180)
            saved = artifact.read_text(encoding="utf-8")
            self.assertNotIn("Authorization", saved)
            self.assertNotIn("Bearer", saved)
            self.assertNotIn("api-key-sentinel", saved)
            record = json.loads(saved)
            self.assertEqual(record["role"], "student_final")
            self.assertFalse(record["request_headers_persisted"])
            self.assertFalse(record["request_body_persisted"])

    def test_monolithic_source_run_locates_problem_as_root_episode(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)
            write_json(source / "problems/root-problem/record.json", {})
            self.assertEqual(locate_episode(source, "root-problem"), source)

    def test_chain_payload_has_only_requested_direct_parent_fields(self):
        parent = ParentMaterial(1, "PARENT_CODE", "WA", sha256_text("PARENT_CODE"),
                                "PARENT_FLAT", sha256_text("PARENT_FLAT"),
                                FLAT_PAYLOAD_RENDERER_VERSION)
        code_only = render_inherited_payload(parent, include_flat=False)
        with_flat = render_inherited_payload(parent, include_flat=True)
        self.assertIn("PARENT_CODE", code_only)
        self.assertIn("# Standardized Verdict\n\nWA", code_only)
        self.assertNotIn("PARENT_FLAT", code_only)
        self.assertEqual(with_flat.replace("\n# Direct-Parent Flat Failure Frontier\n\nPARENT_FLAT\n", "").rstrip(), code_only.rstrip())
        for forbidden in ("Planning", "failure analysis", "generation index", "hidden test"):
            self.assertNotIn(forbidden, code_only)

    def test_balanced_rotation_is_deterministic_and_balanced(self):
        rotations = [condition_rotation(0, i) for i in range(3)]
        self.assertEqual(len(set(rotations)), 3)
        self.assertEqual([x[0] for x in rotations], list(CONDITIONS))
        self.assertEqual(condition_rotation(2, 4), condition_rotation(2, 4))

    def test_all_standardized_failure_verdicts_are_inheritable(self):
        for verdict in ("WA", "RE", "CE", "TLE", "MLE"):
            parent = ParentMaterial(1, "class Solution: pass", verdict, "h")
            payload = render_inherited_payload(parent, include_flat=False)
            self.assertIn(f"# Standardized Verdict\n\n{verdict}", payload)

    def test_chain_prompt_files_share_wrapper_and_flat_only_adds_block(self):
        parent = ParentMaterial(0, "CODE", "WA", "h", "FLAT", "f",
                                FLAT_PAYLOAD_RENDERER_VERSION)
        direct = render_inherited_payload(parent, include_flat=False)
        flat = render_inherited_payload(parent, include_flat=True)
        self.assertTrue(flat.startswith(direct.rstrip()))
        self.assertEqual(flat.count("# Direct-Parent Flat Failure Frontier"), 1)


class IterativeEndToEndTests(unittest.TestCase):
    def test_fresh_five_teacher_all_ac_skips_every_student(self):
        ac = "```python\nOFFLINE_AC=True\nclass Solution:\n    pass\n```"
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            config = FreshTeacherConfig(
                base_pilot_config=str(BASE_CONFIG),
                output_root=str(temp / "out"), teacher_repeats=5,
                max_generations=5, conditions=COMPARISON_V2_CONDITIONS,
                mode="live", source_path=str(temp / "fresh.json"),
            )
            model = ScriptedOfflineModel({"teacher": [ac] * 155})
            judge = DeterministicFakeJudge()
            result = FreshTeacherLineageRunner(
                config, project_root=ROOT, model=model, judge=judge,
                image_id="offline-image",
            ).run("fresh-five")
            self.assertEqual(result["teacher_samples"], 155)
            self.assertEqual(result["teacher_ac"], 155)
            self.assertEqual(result["lineage_aggregate"]["lineages_total"], 0)
            self.assertEqual(judge.calls, 155)
            self.assertEqual(len(model.calls), 310)

    def test_fresh_teacher_failure_flows_into_three_five_generation_lineages(self):
        ac = "```python\nOFFLINE_AC=True\nclass Solution:\n    pass\n```"
        wa = "```python\nclass Solution:\n    pass\n```"
        organizer = json.dumps({
            "evidence_grounded_inferences": [{
                "claim": "The submitted program defines a Solution class.",
                "evidence": "The submitted source contains class Solution.",
                "evidence_sources": ["TEACHER_SUBMITTED_CODE"],
                "support_status": "PROVISIONALLY_SUPPORTED",
                "reproducibility_note": "Direct source inspection.",
                "organizer_source": "FF_ORGANIZER",
            }],
            "selected_low_confidence_excerpts": [],
            "organizer_hypotheses": [],
        })
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            config = FreshTeacherConfig(
                base_pilot_config=str(BASE_CONFIG),
                output_root=str(temp / "out"), teacher_repeats=5,
                max_generations=5, conditions=COMPARISON_V2_CONDITIONS,
                mode="live", source_path=str(temp / "fresh.json"),
            )
            model = ScriptedOfflineModel({
                "teacher": [wa] + [ac] * 154,
                "failure": sum((["Failure analysis.", organizer]
                                for _ in range(5)), []),
            })
            judge = DeterministicFakeJudge()
            result = FreshTeacherLineageRunner(
                config, project_root=ROOT, model=model, judge=judge,
                image_id="offline-image",
            ).run("fresh-one-failure")
            self.assertEqual(result["teacher_samples"], 155)
            self.assertEqual(result["teacher_failures"], 1)
            self.assertEqual(result["lineage_root_eligible"], 1)
            aggregate = result["lineage_aggregate"]
            self.assertEqual(aggregate["lineages_total"], 3)
            self.assertEqual(aggregate["valid_parsed_lineage_manifests"], 3)
            self.assertTrue(all(
                metrics["lineages"] == 1
                for metrics in aggregate["conditions"].values()))
            self.assertTrue(all(
                metrics["completed_unsolved_rate"] == 1
                for metrics in aggregate["conditions"].values()))

    def _run(self, temp, *, finals=None, generations=2, flat=None, run_id="run"):
        source = make_source(temp)
        model = ScriptedOfflineModel(finals)
        judge = DeterministicFakeJudge()
        flat = flat or DeterministicFlatPipeline()
        runner = IterativeRunner(make_config(temp, source, generations=generations),
                                 project_root=ROOT, model=model, judge=judge,
                                 flat_pipeline=flat, image_id="offline-image")
        return runner.run(run_id), runner, model, judge, flat

    def test_full_mock_chain_inheritance_prompt_isolation_and_costs(self):
        with tempfile.TemporaryDirectory() as td:
            result, runner, model, judge, flat = self._run(Path(td), generations=2)
            self.assertEqual(result["lineages_total"], 3)
            run_dir = runner.run_dir
            independent = next(run_dir.glob("lineages/*independent_restart_v1"))
            for payload in independent.glob("generations/generation_*/inherited_payload.txt"):
                self.assertEqual(payload.read_text(encoding="utf-8"), "")
            chain = next(run_dir.glob("lineages/*__code_verdict_chain_v1"))
            gen1 = (chain / "generations/generation_001/inherited_payload.txt").read_text(encoding="utf-8")
            gen2 = (chain / "generations/generation_002/inherited_payload.txt").read_text(encoding="utf-8")
            self.assertIn("ROOT_SENTINEL", gen1)
            self.assertNotIn("ROOT_PLANNING_SENTINEL", gen1)
            self.assertNotIn("ROOT_SENTINEL", gen2)
            flat_chain = next(run_dir.glob("lineages/*code_verdict_flat_ff_chain_v1"))
            flat1 = (flat_chain / "generations/generation_001/inherited_payload.txt").read_text(encoding="utf-8")
            flat2 = (flat_chain / "generations/generation_002/inherited_payload.txt").read_text(encoding="utf-8")
            self.assertIn("ROOT_FLAT_SENTINEL", flat1)
            self.assertNotIn("ROOT_FLAT_SENTINEL", flat2)
            self.assertIn("Offline Flat FF", flat2)
            self.assertEqual(result["conditions"][CONDITIONS[2]]["flat_ff_generation_calls"], 2)
            self.assertEqual(judge.calls, 6)
            self.assertFalse(model.accessed_real_api)
            self.assertFalse(judge.accessed_real_judge)

    def test_stop_on_ac_and_first_ac_cost(self):
        ac = "```python\nOFFLINE_AC=True\nclass Solution:\n    pass\n```"
        with tempfile.TemporaryDirectory() as td:
            result, runner, model, judge, _ = self._run(
                Path(td), generations=5, finals={condition: [ac] for condition in CONDITIONS})
            self.assertEqual(judge.calls, 3)
            for metrics in result["conditions"].values():
                self.assertEqual(metrics["success_within_1_generations"], 1.0)
                self.assertEqual(metrics["mean_generations_to_first_ac"], 1)

    def test_no_code_terminates_chains_but_independent_continues(self):
        no_code = "I failed to provide a fenced source block."
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, judge, _ = self._run(
                Path(td), generations=2,
                finals={condition: [no_code, no_code] for condition in CONDITIONS})
            summaries = [read_json(p) for p in runner.run_dir.glob("lineages/*/lineage_summary.json")]
            outcomes = {x["condition"]: x for x in summaries}
            self.assertEqual(outcomes[CONDITIONS[0]]["generations_attempted"], 2)
            self.assertEqual(outcomes[CONDITIONS[0]]["outcome"], "COMPLETED_UNSOLVED")
            self.assertEqual(outcomes[CONDITIONS[1]]["outcome"], "TERMINATED_NO_INHERITABLE_CODE")
            self.assertEqual(outcomes[CONDITIONS[2]]["outcome"], "TERMINATED_NO_INHERITABLE_CODE")
            self.assertEqual(judge.calls, 0)

    def test_flat_protocol_failure_terminates_without_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, flat = self._run(
                Path(td), generations=3, flat=DeterministicFlatPipeline(fail=True))
            summary = read_json(next(runner.run_dir.glob(
                "lineages/*code_verdict_flat_ff_chain_v1/lineage_summary.json")))
            self.assertEqual(summary["outcome"], "TERMINATED_FLAT_FF_PROTOCOL_FAILURE")
            self.assertEqual(summary["generations_attempted"], 1)
            self.assertTrue(next(runner.run_dir.glob(
                "lineages/*code_verdict_flat_ff_chain_v1/generations/generation_001/flat_ff_protocol_failure.json")).is_file())

    def test_resume_reuses_solver_judge_and_flat_stages(self):
        with tempfile.TemporaryDirectory() as td:
            result, runner, model, judge, flat = self._run(Path(td), generations=2)
            counts = (len(model.calls), judge.calls, flat.calls)
            resumed = IterativeRunner(runner.config, project_root=ROOT, model=model,
                                      judge=judge, flat_pipeline=flat,
                                      image_id="offline-image")
            self.assertEqual(resumed.run("run"), result)
            self.assertEqual((len(model.calls), judge.calls, flat.calls), counts)

    def test_resume_after_planning_does_not_repeat_planning(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td); source = make_source(temp)
            model = FailOnceFinalModel(); judge = DeterministicFakeJudge()
            config = make_config(temp, source, generations=1)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=DeterministicFlatPipeline(),
                            image_id="offline-image").run("resume-planning")
            planning_before = sum(c["role"].endswith("_planning") and
                                  c["condition"] == CONDITIONS[0] for c in model.calls)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=DeterministicFlatPipeline(),
                            image_id="offline-image").run("resume-planning")
            planning_after = sum(c["role"].endswith("_planning") and
                                 c["condition"] == CONDITIONS[0] for c in model.calls)
            self.assertEqual((planning_before, planning_after), (1, 1))

    def test_resume_after_final_does_not_repeat_model_calls_before_judge(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td); source = make_source(temp)
            model = ScriptedOfflineModel(); judge = FailOnceJudge()
            config = make_config(temp, source, generations=1)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=DeterministicFlatPipeline(),
                            image_id="offline-image").run("resume-judge")
            independent_calls = sum(c["condition"] == CONDITIONS[0] for c in model.calls)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=DeterministicFlatPipeline(),
                            image_id="offline-image").run("resume-judge")
            self.assertEqual(sum(c["condition"] == CONDITIONS[0] for c in model.calls), independent_calls)

    def test_completed_flat_generation_is_not_repeated_when_validation_resumes(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td); source = make_source(temp)
            model = ScriptedOfflineModel(); judge = DeterministicFakeJudge()
            flat = TwoPhaseFlatFixture(); config = make_config(temp, source, generations=2)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=flat, image_id="offline-image").run("resume-flat")
            self.assertEqual(flat.generate_calls, 1)
            IterativeRunner(config, project_root=ROOT, model=model, judge=judge,
                            flat_pipeline=flat, image_id="offline-image").run("resume-flat")
            self.assertEqual(flat.generate_calls, 1)
            self.assertEqual(flat.validate_calls, 2)

    def test_parent_and_source_hash_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td), generations=2)
            root_manifest = next(runner.run_dir.glob("source_roots/*.json"))
            root = read_json(root_manifest)
            code_path = Path(root["artifacts"]["teacher_code"]["path"])
            code_path.write_text("drift", encoding="utf-8")
            root["artifacts"]["teacher_code"]["sha256"] = sha256_text("drift")
            unsigned = dict(root); unsigned.pop("root_manifest_sha256")
            root["root_manifest_sha256"] = canonical_hash(unsigned)
            write_json(root_manifest, root)
            with self.assertRaisesRegex(ValueError, "run manifest drift"):
                IterativeRunner(runner.config, project_root=ROOT,
                    model=ScriptedOfflineModel(), judge=DeterministicFakeJudge(),
                    flat_pipeline=DeterministicFlatPipeline(), image_id="offline-image").run("run")

    def test_parent_flat_hash_drift_is_detected_on_resume(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td), generations=2)
            lineage = next(runner.run_dir.glob("lineages/*code_verdict_flat_ff_chain_v1"))
            root_generation = read_json(lineage / "generations/generation_000_root/generation.json")
            root_generation["flat_ff_sha256"] = "drift"
            write_json(lineage / "generations/generation_000_root/generation.json", root_generation)
            summary = read_json(lineage / "lineage_summary.json")
            with self.assertRaisesRegex(ValueError, "parent Flat FF hash drift"):
                runner._validate_lineage_links(lineage, summary)

    def test_descendant_parent_code_artifact_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td), generations=2)
            lineage = next(runner.run_dir.glob("lineages/*__code_verdict_chain_v1"))
            code = lineage / "generations/generation_001/solver/final/extracted_solution.py"
            code.write_text("class Solution:\n    DRIFT = True\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "generation code hash drift"):
                runner._validate_lineage_links(
                    lineage, read_json(lineage / "lineage_summary.json"))

    def test_max_generation_bound_is_exact(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, judge, _ = self._run(Path(td), generations=3)
            summaries = [read_json(path) for path in runner.run_dir.glob("lineages/*/lineage_summary.json")]
            self.assertTrue(all(x["generations_attempted"] == 3 for x in summaries))
            self.assertEqual(judge.calls, 9)

    def test_baseline_prompt_is_byte_equal_to_existing_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td), generations=1)
            call = read_json(next(runner.run_dir.glob(
                "lineages/*independent_restart_v1/generations/generation_001/solver/planning/model_call.json")))
            from experiments.pilot.config import load_config
            from experiments.iterative.adapter import LineagePilotAdapter
            cfg = load_config(BASE_CONFIG)
            adapter = LineagePilotAdapter(cfg, None, judge=object(), project_root=ROOT)
            expected = adapter._rendered_solver_call(
                "planning", "student", FIRST_PROBLEM, "baseline",
                call["user_prompt"])["system_prompt"]
            self.assertEqual(call["system_prompt"], expected)
            self.assertNotIn("Inherited Failure Material", call["user_prompt"])

    def test_dry_run_accesses_neither_api_nor_judge(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            config = make_config(temp, temp / "unused", mode="dry-run")
            result = IterativeRunner(config, project_root=ROOT).dry_run("audit")
            self.assertFalse(result["api_accessed"])
            self.assertFalse(result["judge_accessed"])
            self.assertFalse(result["formal_experiment_started"])

    def test_historical_prompts_and_manifests_are_unmodified(self):
        import subprocess
        protected = ["experiments/prompts/solver_planning.md",
                     "experiments/prompts/solver_final.md",
                     "experiments/prompts/direct_ff_v2.md",
                     "experiments/pilot/provenance_ff.py",
                     "experiments/baseline_v3/baseline_manifest.json",
                     "experiments/baseline_v3_expanded/baseline_manifest.json"]
        changed = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *protected],
                                 cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(changed, "")


class FlatV2RendererTests(unittest.TestCase):
    def test_structured_renderer_preserves_entries_and_removes_only_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            source = make_v2_source(Path(td))
            record_path = next(source.rglob("failure_frontier_record.json"))
            record = read_json(record_path)
            rendered = render_lineage_flat_analysis(record)
            text = rendered.text
            for sentinel in (
                "INFERENCE_CLAIM_SENTINEL", "INFERENCE_EVIDENCE_SENTINEL",
                "REPRODUCIBILITY_SENTINEL", "EXACT_PLANNING_EXCERPT",
                "ORGANIZER_HYPOTHESIS_SENTINEL", "EVIDENCE_LIMITATION_SENTINEL",
            ):
                self.assertIn(sentinel, text)
            for forbidden in (
                "DIRECT_FACT", "EVIDENCE_GROUNDED_INFERENCE",
                "LOW_CONFIDENCE_HYPOTHESIS", "PROVISIONALLY_SUPPORTED",
                "PARTIALLY_SUPPORTED", "CONFIDENCE_NOTE_SENTINEL",
                "trust boundary", "provenance-stratified",
            ):
                self.assertNotIn(forbidden, text)
            self.assertEqual(
                [block.entry_kind for block in rendered.blocks],
                ["inference", "exact_excerpt", "organizer_hypothesis"],
            )

    def test_renderer_does_not_blacklist_substantive_entry_text(self):
        with tempfile.TemporaryDirectory() as td:
            source = make_v2_source(Path(td))
            record_path = next(source.rglob("failure_frontier_record.json"))
            record = read_json(record_path)
            record["selected_low_confidence_excerpts"][0][
                "exact_source_excerpt"] = "EXACT_PLANNING_EXCERPT"
            record["selected_low_confidence_excerpts"][0][
                "confidence_note"] = "not model-visible"
            rendered = render_lineage_flat_analysis(record)
            self.assertIn("EXACT_PLANNING_EXCERPT", rendered.text)

    def test_v2_payload_is_code_verdict_base_plus_one_registered_block(self):
        parent = ParentMaterial(
            1, "PARENT_CODE_SENTINEL", "WA", sha256_text("PARENT_CODE_SENTINEL"),
            validated_record_path="record.json",
            validated_record_sha256="r" * 64,
            flat_addon="ADDON_SENTINEL", flat_addon_path="addon.txt",
            flat_addon_sha256=sha256_text("ADDON_SENTINEL"),
            flat_addon_renderer_version=LINEAGE_FLAT_ADDON_RENDERER_VERSION,
        )
        base = render_inherited_payload(parent, include_flat=False)
        treatment = render_inherited_payload_v2(parent)
        self.assertEqual(
            treatment.replace(
                "\n# Direct-Parent Flat Failure Analysis\n\nADDON_SENTINEL\n", ""
            ).rstrip(),
            base.rstrip(),
        )
        self.assertEqual(treatment.count(parent.code), 1)
        self.assertEqual(treatment.count("# Standardized Verdict"), 1)

    def test_root_freeze_persists_distinct_record_and_addon_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            source = make_v2_source(temp)
            root = freeze_root(
                ROOT, source, "root-episode", temp / "root.json",
                require_lineage_flat_addon=True,
            )
            addon = root["lineage_flat_addon"]
            self.assertEqual(
                addon["renderer_version"], LINEAGE_FLAT_ADDON_RENDERER_VERSION)
            self.assertNotEqual(
                addon["flat_addon_sha256"],
                root["artifacts"]["flat_ff_payload"]["sha256"],
            )
            text = Path(root["artifacts"]["lineage_flat_addon"]["path"]).read_text(
                encoding="utf-8")
            self.assertNotIn("ROOT_SENTINEL", text)
            self.assertNotIn("REJECTED_SENTINEL", text)
            self.assertNotIn("ROOT_PLANNING_SENTINEL", text)

    def test_teacher_root_survives_unrelated_downstream_episode_invalidity(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            source = make_v2_source(temp)
            record_path = next(source.glob("episodes/*/problems/*/record.json"))
            record = read_json(record_path)
            record["valid_episode"] = False
            record["validation_error"] = "unrelated_downstream_material_failure"
            write_json(record_path, record)
            root = freeze_root(
                ROOT, source, "root-episode", temp / "frozen/root.json",
                require_lineage_flat_addon=True,
            )
            self.assertTrue(root["root_eligibility"])
            self.assertFalse(root["source_episode_valid"])
            self.assertEqual(
                root["teacher_root_eligibility_policy"],
                "teacher_stage_and_provenance_v2",
            )


class FlatV2EndToEndTests(unittest.TestCase):
    def _run(self, temp: Path, *, generations=2, flat=None, finals=None,
             run_id="flat-v2"):
        source = make_v2_source(temp)
        model = ScriptedOfflineModel(finals)
        judge = DeterministicFakeJudge()
        flat = flat or DeterministicStructuredFlatPipeline()
        runner = IterativeRunner(
            make_v2_config(temp, source, generations=generations),
            project_root=ROOT, model=model, judge=judge,
            flat_pipeline=flat, image_id="offline-image",
        )
        return runner.run(run_id), runner, model, judge, flat

    def test_two_generation_v2_chain_uses_only_direct_parent(self):
        with tempfile.TemporaryDirectory() as td:
            result, runner, model, judge, flat = self._run(Path(td))
            self.assertEqual(result["lineages_total"], 1)
            lineage = next(runner.run_dir.glob("lineages/*"))
            gen1 = lineage / "generations/generation_001"
            gen2 = lineage / "generations/generation_002"
            payload1 = (gen1 / "inherited_payload.txt").read_text(encoding="utf-8")
            payload2 = (gen2 / "inherited_payload.txt").read_text(encoding="utf-8")
            root_code = next((runner.run_dir / "source_roots").glob(
                "*.artifacts/lineage_flat_addon.txt"))
            self.assertIn("ROOT_SENTINEL", payload1)
            self.assertEqual(payload1.count("ROOT_SENTINEL"), 1)
            self.assertNotIn("ROOT_SENTINEL", payload2)
            self.assertNotIn(root_code.read_text(encoding="utf-8"), payload2)
            self.assertIn("boundary risk", payload2)
            self.assertEqual(judge.calls, 2)
            self.assertEqual(flat.calls, 1)
            for gen in (gen1, gen2):
                manifest = read_json(gen / "generation_manifest.json")
                self.assertEqual(manifest["condition_policy"], FLAT_V2_CONDITION)
                self.assertEqual(
                    manifest["flat_addon_renderer_version"],
                    LINEAGE_FLAT_ADDON_RENDERER_VERSION,
                )
                self.assertTrue(manifest["validated_provenance_record"]["path"])
                self.assertTrue(manifest["lineage_flat_addon"]["path"])
                self.assertTrue(manifest["complete_model_visible_payload"]["path"])
            self.assertFalse(model.accessed_real_api)
            self.assertFalse(judge.accessed_real_judge)

    def test_v2_stop_on_ac_does_not_generate_child_addon(self):
        ac = "```python\nOFFLINE_AC=True\nclass Solution:\n    pass\n```"
        with tempfile.TemporaryDirectory() as td:
            result, runner, _, judge, flat = self._run(
                Path(td), generations=2, finals={FLAT_V2_CONDITION: [ac]})
            summary = read_json(next(runner.run_dir.glob(
                "lineages/*/lineage_summary.json")))
            self.assertEqual(summary["outcome"], "SOLVED")
            self.assertEqual(summary["generations_attempted"], 1)
            self.assertEqual(flat.calls, 0)
            self.assertEqual(judge.calls, 1)

    def test_v2_protocol_failure_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(
                Path(td), generations=2,
                flat=DeterministicStructuredFlatPipeline(fail=True))
            summary = read_json(next(runner.run_dir.glob(
                "lineages/*/lineage_summary.json")))
            self.assertEqual(
                summary["outcome"], "TERMINATED_FLAT_FF_PROTOCOL_FAILURE")
            failure = read_json(next(runner.run_dir.glob(
                "lineages/*/generations/generation_001/"
                "flat_ff_protocol_failure.json")))
            self.assertFalse(failure["fallback_used"])

    def test_v2_noop_resume_reuses_solver_judge_and_addon(self):
        with tempfile.TemporaryDirectory() as td:
            result, runner, model, judge, flat = self._run(Path(td))
            counts = (len(model.calls), judge.calls, flat.calls)
            resumed = IterativeRunner(
                runner.config, project_root=ROOT, model=model, judge=judge,
                flat_pipeline=flat, image_id="offline-image")
            self.assertEqual(resumed.run("flat-v2"), result)
            self.assertEqual((len(model.calls), judge.calls, flat.calls), counts)

    def test_v2_renderer_and_addon_hash_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td))
            lineage = next(runner.run_dir.glob("lineages/*"))
            summary = read_json(lineage / "lineage_summary.json")
            gen1_manifest_path = lineage / (
                "generations/generation_001/generation_manifest.json")
            manifest = read_json(gen1_manifest_path)
            manifest["flat_addon_renderer_version"] = "drift"
            write_json(gen1_manifest_path, manifest)
            summary["generations"][0]["flat_addon_renderer_version"] = "drift"
            with self.assertRaisesRegex(ValueError, "renderer-version drift"):
                runner._validate_lineage_links(lineage, summary)

        with tempfile.TemporaryDirectory() as td:
            _, runner, _, _, _ = self._run(Path(td))
            lineage = next(runner.run_dir.glob("lineages/*"))
            summary = read_json(lineage / "lineage_summary.json")
            addon = Path(summary["generations"][0]["lineage_flat_addon"]["path"])
            addon.write_text("drift", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "add-on artifact drift"):
                runner._validate_lineage_links(lineage, summary)

    def test_v2_dry_run_accesses_neither_api_nor_judge(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            config = make_v2_config(temp, temp / "unused", mode="dry-run")
            result = IterativeRunner(config, project_root=ROOT).dry_run("audit-v2")
            self.assertFalse(result["api_accessed"])
            self.assertFalse(result["judge_accessed"])

    def test_three_condition_v2_comparison_uses_configured_registry(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            source = make_v2_source(temp)
            config = replace(
                make_v2_config(temp, source, generations=1),
                conditions=COMPARISON_V2_CONDITIONS,
            )
            runner = IterativeRunner(
                config, project_root=ROOT, model=ScriptedOfflineModel(),
                judge=DeterministicFakeJudge(),
                flat_pipeline=DeterministicStructuredFlatPipeline(),
                image_id="offline-image",
            )
            result = runner.run("comparison-v2")
            self.assertEqual(result["lineages_total"], 3)
            self.assertEqual(result["valid_parsed_lineage_manifests"], 3)
            self.assertEqual(
                set(result["conditions"]), set(COMPARISON_V2_CONDITIONS))


class RealArtifactReplayTests(unittest.TestCase):
    SOURCE = Path(
        "E:/fft-runs/provenance-v2-formal-31/"
        "provenance-v2-formal-31-20260719T003015Z/problems/"
        "lc-3022-minimize-or-of-remaining-elements-using-operations/"
        "teaching_materials/provenance_ff_v2")
    CHILD = Path(
        "E:/fft-runs/minimal-failure-lineage-smoke/"
        "minimal-lineage-smoke-2roots-2gen-20260719T144211Z/lineages/"
        "lc-3022-minimize-or-of-remaining-elements-using-operations__r00__"
        "code_verdict_flat_ff_chain_v1/generations/generation_001/flat_ff/"
        "teaching_materials/provenance_ff_v2")

    @unittest.skipUnless(SOURCE.is_dir() and CHILD.is_dir(),
                         "real lc-3022 replay artifacts are unavailable")
    def test_lc3022_root_and_generation1_structured_record_replay(self):
        root_record = read_json(self.SOURCE / "failure_frontier_record.json")
        child_record = read_json(self.CHILD / "failure_frontier_record.json")
        root_addon = render_lineage_flat_analysis(root_record)
        child_addon = render_lineage_flat_analysis(child_record)
        for addon in (root_addon.text, child_addon.text):
            for marker in (
                "DIRECT_FACT", "EVIDENCE_GROUNDED_INFERENCE",
                "LOW_CONFIDENCE_HYPOTHESIS", "PROVISIONALLY_SUPPORTED",
                "PARTIALLY_SUPPORTED", "Confidence note:", "trust boundary",
            ):
                self.assertNotIn(marker, addon)
        for record, addon in ((root_record, root_addon.text),
                              (child_record, child_addon.text)):
            for item in record["evidence_grounded_inferences"]:
                self.assertIn(item["claim"], addon)
                self.assertIn(item["evidence"], addon)
            for item in record["selected_low_confidence_excerpts"]:
                self.assertIn(item["exact_source_excerpt"], addon)
            for item in record["organizer_hypotheses"]:
                self.assertIn(item["hypothesis"], addon)
        rejected = read_json(self.CHILD / "rejected_low_confidence_excerpts.json")
        for item in rejected["rejected_excerpts"]:
            self.assertNotIn(item["exact_source_excerpt"], child_addon.text)
        root_code = Path(root_record["code_artifact"]).read_text(encoding="utf-8")
        child_code = Path(child_record["code_artifact"]).read_text(encoding="utf-8")
        root_parent = ParentMaterial(
            0, root_code, "WA", sha256_text(root_code),
            validated_record_path=str(self.SOURCE / "failure_frontier_record.json"),
            validated_record_sha256=canonical_hash(root_record),
            flat_addon=root_addon.text, flat_addon_path="root-addon.txt",
            flat_addon_sha256=root_addon.sha256,
            flat_addon_renderer_version=LINEAGE_FLAT_ADDON_RENDERER_VERSION,
        )
        child_parent = ParentMaterial(
            1, child_code, "WA", sha256_text(child_code),
            validated_record_path=str(self.CHILD / "failure_frontier_record.json"),
            validated_record_sha256=canonical_hash(child_record),
            flat_addon=child_addon.text, flat_addon_path="child-addon.txt",
            flat_addon_sha256=child_addon.sha256,
            flat_addon_renderer_version=LINEAGE_FLAT_ADDON_RENDERER_VERSION,
        )
        generation1 = render_inherited_payload_v2(root_parent)
        generation2 = render_inherited_payload_v2(child_parent)
        self.assertEqual(generation1.count(root_code), 1)
        self.assertEqual(generation2.count(child_code), 1)
        self.assertNotIn(root_code, generation2)
        self.assertNotIn(root_addon.text, generation2)
        self.assertEqual(
            file_hash(self.SOURCE / "flat_failure_payload.txt"),
            "bd88c9cd250b745267f768b9360837f108c0cba5ecf47ec99feaf189f8bde6bd",
        )


class AggregationTests(unittest.TestCase):
    def test_system_denominator_curves_costs_transitions_and_export(self):
        def lineage(condition, outcome, first, verdicts):
            generations = [{
                "generation_index": i + 1, "standardized_verdict": verdict,
                "parent_verdict": "WA" if i else None,
                "final_code_extracted": verdict != "CE", "planning_calls": 1,
                "final_calls": 1, "flat_ff_model_calls": 2 if condition == CONDITIONS[2] else 0,
                "judge_submissions": verdict != "CE", "student_total_tokens": 10,
                "flat_ff_total_tokens": 5 if condition == CONDITIONS[2] else 0,
                "normalized_code_edit_ratio": .5 if i else None,
                "exact_code_repeat": False if i else None,
                "code_sha256": str(i), "parent_code_sha256": str(i-1) if i else None,
                "parent_flat_ff_sha256": None,
            } for i, verdict in enumerate(verdicts)]
            return {"condition": condition, "problem_id": "p", "root_episode_id": "r",
                    "lineage_repeat_index": 0, "outcome": outcome,
                    "first_ac_generation": first, "system_attempt_valid": True,
                    "solver_calls": len(generations)*2,
                    "flat_ff_model_calls": sum(g["flat_ff_model_calls"] for g in generations),
                    "judge_submissions": sum(g["judge_submissions"] for g in generations),
                    "student_tokens": len(generations)*10,
                    "flat_ff_tokens": sum(g["flat_ff_total_tokens"] for g in generations),
                    "generations": generations}
        rows = [lineage(CONDITIONS[0], "SOLVED", 2, ["WA", "AC"]),
                lineage(CONDITIONS[1], "TERMINATED_NO_INHERITABLE_CODE", None, ["CE"]),
                lineage(CONDITIONS[2], "SOLVED", 1, ["AC"])]
        result = aggregate_run(rows, 2, CONDITIONS)
        self.assertEqual(result["conditions"][CONDITIONS[0]]["success_within_1_generations"], 0)
        self.assertEqual(result["conditions"][CONDITIONS[0]]["success_within_2_generations"], 1)
        self.assertEqual(result["conditions"][CONDITIONS[1]]["code_extraction_failure_rate"], 1)
        self.assertGreater(result["conditions"][CONDITIONS[2]]["total_model_calls"], 2)
        transitions = transition_rows(rows)
        self.assertEqual(transitions[-1]["cumulative_total_model_calls"], 4)

    def test_aggregate_conditions_are_dynamic_and_manifest_count_is_exact(self):
        rows = [{
            "lineage_id": f"lineage-{condition}", "condition": condition,
            "problem_id": "p", "root_episode_id": "r",
            "lineage_repeat_index": 0, "outcome": "COMPLETED_UNSOLVED",
            "first_ac_generation": None, "system_attempt_valid": True,
            "solver_calls": 0, "flat_ff_model_calls": 0,
            "judge_submissions": 0, "student_tokens": 0,
            "flat_ff_tokens": 0, "generations": [],
        } for condition in COMPARISON_V2_CONDITIONS]
        manifests = [{
            "lineage_id": row["lineage_id"], "condition": row["condition"],
            "problem_id": row["problem_id"],
        } for row in rows]
        result = aggregate_run(
            rows, 3, COMPARISON_V2_CONDITIONS,
            parsed_lineage_manifests=manifests,
        )
        self.assertEqual(set(result["conditions"]), set(COMPARISON_V2_CONDITIONS))
        self.assertEqual(result["lineages_total"], len(manifests))
        self.assertEqual(result["valid_parsed_lineage_manifests"], len(manifests))
        with self.assertRaisesRegex(ValueError, "lineage count"):
            aggregate_run(
                rows[:-1], 3, COMPARISON_V2_CONDITIONS,
                parsed_lineage_manifests=manifests,
            )
        with self.assertRaisesRegex(ValueError, "aggregate conditions"):
            aggregate_run(rows, 3, CONDITIONS)

    def test_lineage_manifest_parser_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            path = run_dir / "lineages/bad/lineage_manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid lineage manifest"):
                parse_lineage_manifests(run_dir)


if __name__ == "__main__":
    unittest.main()
