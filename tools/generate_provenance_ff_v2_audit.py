from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pilot.config import load_config
from experiments.pilot.orchestrator import PilotRunner
from experiments.pilot.provenance_ff import (
    CRITICAL_CONDITION, DIRECT_CONDITION, FLAT_CONDITION,
    EvidenceGroundedInference,
    FailureFrontierRecord, OrganizerHypothesis, SelectedLowConfidenceExcerpt,
    SourceArtifact, render_flat_failure_payload, render_shared_failure_payload,
    sha256_text,
    teacher_final_natural_language, validate_direct_instruction,
)


PROBLEM_IDS = (
    "lc-1786-number-of-restricted-paths-from-first-to-last-node",
    "lc-1851-minimum-interval-to-include-each-query",
    "lc-2809-minimum-time-to-make-array-sum-at-most-x",
    "lc-2940-find-building-where-alice-and-bob-can-meet",
    "lc-2945-find-maximum-non-decreasing-array-length",
    "lc-3022-minimize-or-of-remaining-elements-using-operations",
    "lc-3077-maximum-strength-of-k-disjoint-subarrays",
)
LEGACY_PROMPT_HASHES = {
    "failure_frontier.md": "cd7c0417304e1918e0d7e6dc7399a20163d8382ecda7908f90d08cb4abc453b9",
    "failure_frontier_user.md": "d6b987ccc60f7045a8315bd178b3df227a2f559791782af4e96fac0c7c3fc118",
    "student_user_with_material.md": "2a2c5d10efac68b1ab742ee43bc519a783ca4a8caf974452b7ff74f3f703dc05",
    "student_user_with_critical_ff.md": "0c701c74810a379f36fc709de9d14baa7b723503e02c2e23759b05ef10268008",
    "solver_planning.md": "fd1c48daa284aeb7251827bdc9a479b22bfe1d1f4252fae8c9b2e3e2fb574bca",
    "solver_final.md": "6c0aa3cf4c0aa914176bfd5e4b0ba994512aa43b14082df6e0fd1f772adf5271",
    "solver_final_user.md": "a951d46edf671b6930c3715f4f46a20f7a2a60572e3e008568d2427b8ced1d3a",
    "success_teaching.md": "3f43c45654901ffe47cbcba2b41e03c18b16c090c0bd9cd0f022cdc2a8edd7a4",
    "success_teaching_user.md": "0c247fec683ee7d88fab3187310d5c71abde7b56acc22355fa6343b75cf0c481",
}


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2,
                                sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rendered(call: dict[str, str]) -> str:
    return ("=== SYSTEM PROMPT ===\n" + call["system_prompt"] +
            "\n=== USER PROMPT ===\n" + call["user_prompt"])


def text_diff(left: str, right: str, left_name: str, right_name: str) -> str:
    return "".join(difflib.unified_diff(
        left.splitlines(keepends=True), right.splitlines(keepends=True),
        fromfile=left_name, tofile=right_name,
    ))


def actual_chain() -> dict[str, object]:
    return {
        "legacy_teacher_failure": [
            "PilotRunner._run_problem",
            "PilotRunner._solver_stage(teacher): solver_planning.md + formatted_problem",
            "PilotRunner._solver_stage(teacher): solver_final.md + solver_final_user.md",
            "DockerJudge.judge(hidden)",
            "PilotRunner._failure_material",
            "failure_frontier.md + failure_frontier_user.md",
            "PilotRunner._matched_guidance (legacy token-interval policy)",
            "PilotRunner._solver_stage for success_only/failure_frontier/critical_failure_frontier/general_guidance",
        ],
        "provenance_v2_teacher_failure": [
            "PilotRunner._run_problem",
            "PilotRunner._solver_stage(teacher): solver_planning.md + formatted_problem",
            "PilotRunner._solver_stage(teacher): solver_final.md + solver_final_user.md",
            "DockerJudge.judge(hidden)",
            "standardized_error_type (submission-level type only)",
            "PilotRunner._provenance_failure_material",
            "teacher_failure_analysis_v2.md + teacher_failure_analysis_v2_user.md",
            "ff_organizer_v2.md + ff_organizer_v2_user.md",
            "parse_organizer_record + shared and flat deterministic payload renderers",
            "PilotRunner._matched_guidance (semantic_complete_no_length_v2; no token interval gate)",
            "PilotRunner._solver_stage for baseline/direct_ff_v2/critical_ff_v2/flat_ff_v2/general_guidance",
        ],
        "teacher_success": [
            "PilotRunner._success_material",
            "success_teaching.md + success_teaching_user.md",
            "byte-identical success material supplied to every configured Student",
        ],
        "rendering": [
            "PromptRenderer.formatted_problem",
            "PilotRunner._rendered_call",
            "PilotRunner._rendered_solver_call",
            "solver_final_user.md adds only the same role's Planning",
        ],
        "persistence_resume": [
            "PilotRunner._call validates persisted max tokens, prompt hash, model and sampling fields",
            "PilotRunner._solver_stage reuses completed state/submission",
            "v2 source_manifest.json locks source hashes, policy versions, record hash and both payload hashes",
        ],
        "eligibility": "Existing eligibility.py remains unchanged; INTERNAL_ERROR maps to JUDGE_ERROR and exits before any failure material.",
    }


def generate(root: Path, source_root: Path, output: Path) -> dict[str, object]:
    config = load_config(root / "experiments/configs/provenance_stratified_ff_v2.example.yaml")
    runner = PilotRunner(config, None, judge=object(), project_root=root)
    prompt_root = root / "experiments/prompts"
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "actual_prompt_call_chain.json", actual_chain())

    prompt_map = {
        "teacher_failure_analysis_v2_prompt.txt": "teacher_failure_analysis_v2.md",
        "ff_organizer_v2_prompt.txt": "ff_organizer_v2.md",
        "baseline_v2_prompt.txt": "baseline_v2.md",
        "direct_ff_v2_prompt.txt": "direct_ff_v2.md",
        "critical_ff_v2_prompt.txt": "critical_ff_v2.md",
        "gg_material_no_length_v2_prompt.txt":
            "general_guidance_material_no_length_v2.md",
    }
    for target, source in prompt_map.items():
        write_text(output / target, (prompt_root / source).read_text(encoding="utf-8"))
    direct_instruction = (prompt_root / "direct_ff_v2.md").read_text(encoding="utf-8")
    critical_instruction = (prompt_root / "critical_ff_v2.md").read_text(encoding="utf-8")
    validate_direct_instruction(direct_instruction)
    write_text(output / "direct_vs_critical_static_diff.txt", text_diff(
        direct_instruction, critical_instruction, "direct_ff_v2", "critical_ff_v2"))
    write_text(output / "classification_examples.md", """# Classification examples

- Raw standardized final error type, exact submitted code, its SHA-256, and exact raw excerpts are `DIRECT_FACT`.
- “The code contains nested loops” and a short reproducible complexity analysis produced by the organizer are `EVIDENCE_GROUNDED_INFERENCE`, never facts.
- Every Teacher claim, including algorithm, proof, complexity, attempted method, and failure diagnosis, is `LOW_CONFIDENCE_HYPOTHESIS`.
- “The quadratic complexity caused the timeout” is a low-confidence causal hypothesis because the final error type cannot identify a unique cause.
- Ambiguity fails closed to `LOW_CONFIDENCE_HYPOTHESIS`.
""")

    results: dict[str, object] = {}
    for problem_id in PROBLEM_IDS:
        source = source_root / "materials" / problem_id
        problem = (source / "formatted_problem.md").read_text(encoding="utf-8")
        planning_text = (source / "teacher_planning.md").read_text(encoding="utf-8")
        final_raw = (source / "teacher_final.md").read_text(encoding="utf-8")
        code = (source / "teacher_code.py").read_text(encoding="utf-8").rstrip("\n")
        final_nl_text = teacher_final_natural_language(final_raw, code)
        failure_text = (
            "Representative offline fixture: I am uncertain which assumption or "
            "implementation detail is associated with the standardized failure. "
            "This is not a root-cause claim."
        )
        sources = {
            "TEACHER_PLANNING": SourceArtifact.create(
                "TEACHER_PLANNING", "teacher/planning/content.md", planning_text),
            "TEACHER_FINAL_NATURAL_LANGUAGE": SourceArtifact.create(
                "TEACHER_FINAL_NATURAL_LANGUAGE",
                "teacher/final/natural_language.md", final_nl_text),
            "TEACHER_FAILURE_ANALYSIS": SourceArtifact.create(
                "TEACHER_FAILURE_ANALYSIS",
                "teacher_failure_analysis/content.md", failure_text),
        }
        excerpt = planning_text.strip().splitlines()[0][:180]
        low = () if not excerpt else (SelectedLowConfidenceExcerpt(
            source_type="TEACHER_PLANNING",
            source_artifact=sources["TEACHER_PLANNING"].source_artifact,
            source_sha256=sources["TEACHER_PLANNING"].source_sha256,
            exact_source_excerpt=excerpt,
            confidence_note="Teacher-generated natural language; unverified.",
        ),)
        code_excerpt = code.splitlines()[0]
        record = FailureFrontierRecord(
            policy_version="provenance_stratified_ff_v2",
            final_error_type="WRONG_ANSWER",
            code_artifact="teacher/final/extracted_solution.py",
            code_sha256=sha256_text(code),
            planning_artifact=sources["TEACHER_PLANNING"].source_artifact,
            failure_analysis_artifact=sources[
                "TEACHER_FAILURE_ANALYSIS"].source_artifact,
            evidence_grounded_inferences=(EvidenceGroundedInference(
                claim="The submitted artifact begins with the quoted exact line.",
                evidence=code_excerpt,
                evidence_sources=("TEACHER_SUBMITTED_CODE",),
                support_status="PROVISIONALLY_SUPPORTED",
                reproducibility_note="Compare the evidence with the first submitted-code line.",
            ),),
            selected_low_confidence_excerpts=low,
            organizer_hypotheses=(OrganizerHypothesis(
                hypothesis="A visible assumption may require further checking.",
                evidence_limitation="The standardized error type does not identify a cause.",
            ),),
        )
        payload = render_shared_failure_payload(
            final_error_type="WRONG_ANSWER", code=code,
            code_artifact=record.code_artifact,
            planning=sources["TEACHER_PLANNING"],
            final_natural_language=sources["TEACHER_FINAL_NATURAL_LANGUAGE"],
            failure_analysis=sources["TEACHER_FAILURE_ANALYSIS"], record=record)
        flat_payload = render_flat_failure_payload(
            final_error_type="WRONG_ANSWER", code=code,
            code_artifact=record.code_artifact,
            planning=sources["TEACHER_PLANNING"],
            final_natural_language=sources["TEACHER_FINAL_NATURAL_LANGUAGE"],
            failure_analysis=sources["TEACHER_FAILURE_ANALYSIS"], record=record)
        source_blocks = "\n\n".join(
            f'<LOW_CONFIDENCE_SOURCE type="{item.source_type}">\n'
            f'Artifact: {item.source_artifact}\nSHA-256: {item.source_sha256}\n'
            f'Verbatim content:\n{item.content}\n</LOW_CONFIDENCE_SOURCE>'
            for item in sources.values())
        source_meta = json.dumps({key: {
            "source_type": item.source_type,
            "source_artifact": item.source_artifact,
            "source_sha256": item.source_sha256,
        } for key, item in sources.items()}, ensure_ascii=False, sort_keys=True)
        analysis_call = runner._rendered_call(
            "teacher_failure_analysis_v2", problem_id, "failure", problem,
            teacher_planning=planning_text,
            teacher_final_natural_language=final_nl_text,
            teacher_code=code, final_error_type="WRONG_ANSWER")
        organizer_call = runner._rendered_call(
            "ff_organizer_v2", problem_id, "failure", problem,
            low_confidence_sources=source_blocks, teacher_code=code,
            final_error_type="WRONG_ANSWER", source_metadata_json=source_meta)
        baseline = runner._rendered_solver_call(
            "planning", "student", problem_id, "baseline", problem)
        direct = runner._rendered_solver_call(
            "planning", "student", problem_id, DIRECT_CONDITION, problem,
            additional_material=payload)
        critical = runner._rendered_solver_call(
            "planning", "student", problem_id, CRITICAL_CONDITION, problem,
            additional_material=payload)
        flat = runner._rendered_solver_call(
            "planning", "student", problem_id, FLAT_CONDITION, problem,
            additional_material=flat_payload)
        direct_final = runner._rendered_solver_call(
            "final", "student", problem_id, DIRECT_CONDITION, problem,
            additional_material=payload, planning_content="<ROLE_PLANNING>",
            planning_status="<PLANNING_STATUS>")
        critical_final = runner._rendered_solver_call(
            "final", "student", problem_id, CRITICAL_CONDITION, problem,
            additional_material=payload, planning_content="<ROLE_PLANNING>",
            planning_status="<PLANNING_STATUS>")
        flat_final = runner._rendered_solver_call(
            "final", "student", problem_id, FLAT_CONDITION, problem,
            additional_material=flat_payload, planning_content="<ROLE_PLANNING>",
            planning_status="<PLANNING_STATUS>")
        target = output / problem_id
        files = {
            "rendered_teacher_failure_analysis_request.txt": rendered(analysis_call),
            "rendered_ff_organizer_request.txt": rendered(organizer_call),
            "rendered_baseline_planning.txt": rendered(baseline),
            "rendered_direct_planning.txt": rendered(direct),
            "rendered_critical_planning.txt": rendered(critical),
            "rendered_flat_planning.txt": rendered(flat),
            "rendered_direct_shared_payload.txt": payload,
            "rendered_critical_shared_payload.txt": payload,
            "rendered_flat_payload.txt": flat_payload,
            "rendered_direct_final_static.txt": direct_final["system_prompt"],
            "rendered_critical_final_static.txt": critical_final["system_prompt"],
            "rendered_flat_final_static.txt": flat_final["system_prompt"],
            "direct_vs_critical_diff.txt": text_diff(
                direct["user_prompt"], critical["user_prompt"], "direct", "critical"),
        }
        for name, content in files.items():
            write_text(target / name, content)
        hashes = {name: digest(target / name) for name in files}
        write_json(target / "prompt_hashes.json", hashes)
        leakage = {
            "only_standardized_error_type_exposed": "WRONG_ANSWER" in payload,
            "no_internal_judge_record_in_payload": all(
                marker not in payload for marker in (
                    "public_tests_all_passed", "internal_result", "runtime_ms",
                    "judge.internal.json", "expected_output", "actual_output")),
            "direct_critical_payload_byte_equal": (
                (target / "rendered_direct_shared_payload.txt").read_bytes() ==
                (target / "rendered_critical_shared_payload.txt").read_bytes()),
            "flat_uses_direct_prompt": (
                direct["system_prompt"] == flat["system_prompt"] and
                direct["user_prompt"].replace(payload, "<MATERIAL>") ==
                flat["user_prompt"].replace(flat_payload, "<MATERIAL>")),
            "flat_contains_all_raw_sources": all(
                item.content in flat_payload for item in sources.values()),
            "flat_contains_exact_code_once": flat_payload.count(code) == 1,
            "flat_has_no_confidence_tier_markers": all(
                marker not in flat_payload for marker in (
                    "DIRECT_FACT_SOURCE", "LOW_CONFIDENCE_SOURCE",
                    "EVIDENCE_GROUNDED_INFERENCE", "LOW_CONFIDENCE_HYPOTHESIS")),
        }
        classification = {
            "complete_planning_low_confidence": planning_text in payload,
            "complete_failure_analysis_low_confidence": failure_text in payload,
            "complete_code_direct_fact_exactly_once": payload.count(code) == 1,
            "record_does_not_duplicate_full_code": code not in json.dumps(record.to_dict()),
            "record_does_not_duplicate_full_planning": planning_text not in json.dumps(record.to_dict()),
            "all_selected_excerpts_have_provenance": all(
                item.source_type and item.source_artifact and item.source_sha256
                for item in record.selected_low_confidence_excerpts),
        }
        write_json(target / "leakage_audit.json", leakage)
        write_json(target / "classification_audit.json", classification)
        results[problem_id] = {"leakage": leakage, "classification": classification,
                               "hashes": hashes}

    new_prompts = {name: digest(prompt_root / name) for name in (
        "teacher_failure_analysis_v2.md", "teacher_failure_analysis_v2_user.md",
        "ff_organizer_v2.md", "ff_organizer_v2_user.md", "baseline_v2.md",
        "direct_ff_v2.md", "critical_ff_v2.md", "success_teaching_v2.md",
        "success_teaching_v2_user.md",
        "general_guidance_blueprint_no_length_v2.md",
        "general_guidance_blueprint_repair_no_length_v2.md",
        "general_guidance_material_no_length_v2.md",
        "general_guidance_material_repair_no_length_v2.md",
        "general_guidance_truncation_recovery_no_length_v2.md")}
    current_legacy = {name: digest(prompt_root / name)
                      for name in LEGACY_PROMPT_HASHES}
    historical_unchanged = current_legacy == LEGACY_PROMPT_HASHES
    prompt_hashes = {"new": new_prompts, "legacy_expected": LEGACY_PROMPT_HASHES,
                     "legacy_current": current_legacy,
                     "historical_prompts_unchanged": historical_unchanged}
    write_json(output / "prompt_hashes.json", prompt_hashes)
    manifest = {
        "failure_frontier_policy": "provenance_stratified_ff_v2",
        "teacher_failure_analysis_policy": "provenance_preserved_failure_analysis_v2",
        "shared_payload_builder_version": "provenance_payload_builder_v2",
        "flat_payload_renderer_version": "flat_provenance_payload_renderer_v2",
        "rejected_excerpt_policy": "reject_nonverbatim_excerpt_continue_v1",
        "gg_acceptance_policy": "semantic_complete_no_length_v2",
        "gg_token_match_required": False,
        "information_classes": {
            "DIRECT_FACT": {"meaning": "raw objective records only",
                            "model_interpretation_allowed": False,
                            "examples": ["standardized final submission error type",
                                         "exact submitted code", "exact raw code excerpt"]},
            "EVIDENCE_GROUNDED_INFERENCE": {
                "meaning": "fallible FF-organizer analysis grounded in reproducible visible evidence",
                "guaranteed_correct": False,
                "teacher_natural_language_dependency_allowed": False,
                "support_statuses": ["PROVISIONALLY_SUPPORTED", "PARTIALLY_SUPPORTED"]},
            "LOW_CONFIDENCE_HYPOTHESIS": {
                "meaning": "all Teacher natural language and unsupported explanations",
                "provenance_required": True},
        },
        "student_treatments": {
            "baseline_v2": {"visible_material": "public problem only"},
            "direct_ff_v2": {"shared_payload": "provenance-stratified failure materials",
                             "explicit_source_audit": False},
            "critical_ff_v2": {"shared_payload": "byte-identical provenance-stratified failure materials",
                               "explicit_source_audit": True,
                               "review_scope": "only claims materially affecting algorithm correctness"},
            "flat_ff_v2": {
                "visible_information": "the same raw sources and organizer-record fields",
                "payload_presentation": "flat; no confidence-tier grouping or labels",
                "instruction": "byte-identical direct_ff_v2 instruction",
                "explicit_source_audit": False,
            },
        },
        "treatment_differences": {
            "direct_vs_critical": "source-aware selective inheritance instruction",
            "direct_vs_flat": "provenance-tier presentation only",
        },
        "treatment_specific_extra_model_calls": 0,
        "shared_pipeline_model_calls": ["teacher_failure_analysis_v2", "ff_organizer_v2"],
        "judge_effect": "none",
        "eligibility_effect": (
            "GG eligibility requires semantic completeness, content safety, and a "
            "complete stop response; no FF token interval is used"),
        "prompt_hashes": new_prompts,
        "final_static_prompt_sha256": digest(prompt_root / "solver_final.md"),
    }
    write_json(output / "treatment_manifest.json", manifest)
    passed = historical_unchanged and all(
        all(value for value in result[section].values())
        for result in results.values() for section in ("leakage", "classification"))
    summary = {
        "passed": passed, "representative_fixture_count": len(results),
        "historical_prompts_unchanged": historical_unchanged,
        "direct_critical_payload_byte_equal_all": all(
            result["leakage"]["direct_critical_payload_byte_equal"]
            for result in results.values()),
        "direct_critical_final_static_equal_all": all(
            result["hashes"]["rendered_direct_final_static.txt"] ==
            result["hashes"]["rendered_critical_final_static.txt"]
            for result in results.values()),
        "flat_uses_direct_prompt_all": all(
            result["leakage"]["flat_uses_direct_prompt"]
            for result in results.values()),
        "flat_has_no_confidence_tier_markers_all": all(
            result["leakage"]["flat_has_no_confidence_tier_markers"]
            for result in results.values()),
        "real_api_accessed": False, "judge_accessed": False,
        "gg_acceptance_policy": "semantic_complete_no_length_v2",
        "gg_token_match_required": False,
        "source_root_read_only": str(source_root),
    }
    write_json(output / "audit_summary.json", summary)
    write_text(output / "audit_summary.md", "# Provenance-Stratified FF v2 prompt audit\n\n" +
               "\n".join(f"- {key}: `{value}`" for key, value in summary.items()) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output", default="prompt_audits/provenance_stratified_ff_v2")
    args = parser.parse_args()
    root = ROOT
    summary = generate(root, Path(args.source_root).resolve(),
                       (root / args.output).resolve())
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
