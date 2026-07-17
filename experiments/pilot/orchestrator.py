from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import math
import os
import subprocess
import sys

from ffjudge.models import JudgeResult, ProblemSpec, Verdict
from ffjudge.runner import DockerJudge, DockerUnavailableError

from .code_extraction import extract_single_python_code
from .config import PilotConfig, ProblemConfig
from .model_client import ModelClient, ModelInfrastructureError, ModelResponse
from .prompts import PromptRenderer
from .storage import read_json, write_json, write_text


VERDICT_MAP = {
    Verdict.ACCEPTED: "AC",
    Verdict.WRONG_ANSWER: "WA",
    Verdict.SYNTAX_ERROR: "CE",
    Verdict.INVALID_SUBMISSION: "CE",
    Verdict.RUNTIME_ERROR: "RE",
    Verdict.TIME_LIMIT_EXCEEDED: "TLE",
    Verdict.MEMORY_LIMIT_EXCEEDED: "MLE",
    Verdict.INTERNAL_ERROR: "JUDGE_ERROR",
}
STUDENT_CONDITIONS = ("success_only", "failure_frontier", "general_guidance")
GG_REQUIRED_SECTIONS = (
    "## Constraint Analysis",
    "## Plausible Approaches",
    "## Edge Cases",
    "## Implementation Checks",
)


def coarse_verdict(verdict: Verdict) -> str:
    return VERDICT_MAP[verdict]


class PilotRunner:
    def __init__(
        self,
        config: PilotConfig,
        model: ModelClient | None,
        *,
        judge: Any | None = None,
        project_root: str | Path = ".",
    ) -> None:
        self.config = config
        self.model = model
        self.project_root = Path(project_root).resolve()
        self.renderer = PromptRenderer(self._path(config.prompts_dir))
        self.judge = judge or DockerJudge(config.execution.judge_image)
        self.run_dir: Path | None = None

    def _path(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.project_root / candidate

    def verify_baseline(self) -> None:
        verifier_name = (
            "verify_baseline_v2_manifest.py"
            if self.config.baseline_id == "failure-frontier-baseline-v2"
            else "verify_baseline_manifest.py"
        )
        verifier = self.project_root / "tools" / verifier_name
        completed = subprocess.run(
            [sys.executable, str(verifier), "--manifest",
             str(self._path(self.config.baseline_manifest))],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError("baseline manifest verification failed")

    def run(self, run_id: str | None = None) -> dict[str, Any]:
        self.verify_baseline()
        run_id = run_id or datetime.now(timezone.utc).strftime("pilot-%Y%m%dT%H%M%SZ")
        self.run_dir = self._path(self.config.execution.output_root) / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.run_dir / "config.snapshot.yaml", self.config.public_snapshot())
        write_json(self.run_dir / "run.state.json", {
            "run_id": run_id,
            "status": "running",
            "started_at": _now(),
        })
        if self.config.mode == "dry-run":
            result = self._dry_run(run_id)
        else:
            if self.model is None:
                raise ValueError("live and mock modes require a model client")
            records = [self._run_problem(run_id, item) for item in self.config.problems]
            result = build_summary(run_id, records)
            write_text(
                self.run_dir / "results.jsonl",
                "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            )
            write_json(self.run_dir / "summary.json", result)
            write_text(self.run_dir / "summary.md", summary_markdown(result))
        write_json(self.run_dir / "run.state.json", {
            "run_id": run_id,
            "status": "completed",
            "completed_at": _now(),
        })
        return result

    def run_smoke(self, problem_id: str, output_root: str | Path,
                  run_id: str | None = None) -> dict[str, Any]:
        """Run one explicitly selected, non-formal episode outside the repo."""
        self.verify_baseline()
        output = Path(output_root).resolve()
        if output == self.project_root or output.is_relative_to(self.project_root):
            raise ValueError("smoke-test output-root must be outside the repository")
        selected: tuple[ProblemConfig, ...] = tuple(
            item for item in self.config.problems
            if ProblemSpec.load(self._path(item.problem)).problem_id == problem_id
        )
        if len(selected) != 1:
            raise ValueError(f"problem-id must select exactly one configured problem: {problem_id}")
        run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.run_dir = output / "smoke-test" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        metadata = self._smoke_metadata(problem_id)
        write_json(self.run_dir / "version.json", metadata)
        write_json(self.run_dir / "config.snapshot.yaml", self.config.public_snapshot())
        write_json(self.run_dir / "run.state.json", {
            "run_id": run_id, "problem_id": problem_id,
            "status": "running", "started_at": _now(), "informal": True,
        })
        record = self._run_problem(run_id, selected[0])
        audit = self._smoke_audit(record, selected[0])
        result = {
            "run_id": run_id,
            "problem_id": problem_id,
            "informal_smoke_test": True,
            "formal_pilot_data_generated": False,
            "record": record,
            "audit": audit,
            "passed": bool(record.get("valid_episode")) and all(audit.values()),
            "output_directory": str(self.run_dir),
        }
        write_json(self.run_dir / "smoke_result.json", result)
        write_text(self.run_dir / "smoke_report.md", smoke_markdown(result))
        write_json(self.run_dir / "run.state.json", {
            "run_id": run_id, "problem_id": problem_id,
            "status": "completed", "completed_at": _now(),
            "informal": True, "passed": result["passed"],
        })
        return result

    def _smoke_metadata(self, problem_id: str) -> dict[str, Any]:
        config_path = self.project_root / "experiments" / "configs" / "pilot_v1.yaml"
        prompt_hashes = {
            str(path.relative_to(self.project_root)).replace("\\", "/"): _file_hash(path)
            for path in sorted(self._path(self.config.prompts_dir).glob("*.md"))
        }
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.strip()
        tags = subprocess.run(
            ["git", "tag", "--points-at", "HEAD"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.splitlines()
        return {
            "commit_sha": commit,
            "tags": tags,
            "problem_id": problem_id,
            "config_path": str(config_path),
            "config_sha256": _file_hash(config_path),
            "prompt_sha256": prompt_hashes,
        }

    def _smoke_audit(self, record: dict[str, Any], item: ProblemConfig) -> dict[str, bool]:
        assert self.run_dir is not None
        calls = [read_json(path) for path in self.run_dir.rglob("model_call.json")]
        responses = [call.get("response", {}) for call in calls]
        usage_valid = all(
            type(response.get("input_tokens")) is int and response["input_tokens"] >= 0 and
            type(response.get("output_tokens")) is int and response["output_tokens"] > 0 and
            type(response.get("total_tokens")) is int and response["total_tokens"] > 0
            for response in responses
        )
        reasoning_empty = all(
            response.get("reasoning_content") in (None, "") for response in responses)
        key = os.environ.get(self.config.model.api_key_env, "")
        persisted = b"".join(path.read_bytes() for path in self.run_dir.rglob("*")
                             if path.is_file())
        teacher_calls = [call for call in calls if call.get("role") == "teacher"]
        expected_problem = self.renderer.formatted_problem(
            self._path(item.problem), self._path(item.public_tests))
        teacher_public_only = (
            len(teacher_calls) == 1 and
            teacher_calls[0].get("user_prompt") == expected_problem
        )
        baseline_calls = [call for call in calls if call.get("role") == "student" and
                          call.get("condition") == "success_only"]
        baseline_exact = bool(baseline_calls) and (
            record.get("teacher", {}).get("verdict") == "AC" or
            baseline_calls[0].get("user_prompt") == expected_problem
        )
        ff_calls = [call for call in calls if call.get("role") == "student" and
                    call.get("condition") == "failure_frontier"]
        gg_calls = [call for call in calls if call.get("role") == "student" and
                    call.get("condition") == "general_guidance"]
        student_system_equal = bool(ff_calls and gg_calls) and (
            ff_calls[0].get("system_prompt") == gg_calls[0].get("system_prompt"))
        student_calls = [call for call in calls if call.get("role") == "student"]
        success_student_prompts_equal = True
        if record.get("teacher", {}).get("verdict") == "AC":
            success_student_prompts_equal = len(student_calls) == 3 and (
                len({call.get("system_prompt") for call in student_calls}) == 1 and
                len({call.get("user_prompt") for call in student_calls}) == 1
            )
        sentinel_ff = self._rendered_call(
            "student", record["problem_id"], "failure_frontier", expected_problem,
            additional_material="FF_MATERIAL_SENTINEL", success_branch=False)
        sentinel_gg = self._rendered_call(
            "student", record["problem_id"], "general_guidance", expected_problem,
            additional_material="GG_MATERIAL_SENTINEL", success_branch=False)
        framing_equal = (
            sentinel_ff["system_prompt"] == sentinel_gg["system_prompt"] and
            sentinel_ff["user_prompt"].replace("FF_MATERIAL_SENTINEL", "<MATERIAL>") ==
            sentinel_gg["user_prompt"].replace("GG_MATERIAL_SENTINEL", "<MATERIAL>")
        )
        token_match_ok = (
            record.get("teacher", {}).get("verdict") == "AC" or
            record.get("teaching_material", {}).get("token_match_passed") is True
        )
        return {
            "exactly_one_problem": record.get("problem_id") ==
                ProblemSpec.load(self._path(item.problem)).problem_id,
            "teacher_called_once": len(teacher_calls) == 1,
            "teacher_public_information_only": teacher_public_only,
            "all_reasoning_content_empty": reasoning_empty,
            "all_usage_complete": usage_valid,
            "all_requests_non_reasoning": self.config.model.thinking == {"type": "disabled"},
            "baseline_prompt_exact_when_applicable": baseline_exact,
            "ff_gg_student_system_equal": student_system_equal,
            "ff_gg_student_framing_equal_except_material": framing_equal,
            "success_branch_student_prompts_equal": success_student_prompts_equal,
            "token_match_passed_when_applicable": token_match_ok,
            "api_key_not_persisted": not key or key.encode() not in persisted,
            "no_formal_results": not (self.run_dir / "results.jsonl").exists() and
                not (self.run_dir / "summary.json").exists() and
                not (self.run_dir / "summary.md").exists(),
        }

    def _dry_run(self, run_id: str) -> dict[str, Any]:
        assert self.run_dir is not None
        calls: list[dict[str, Any]] = []
        for item in self.config.problems:
            spec = ProblemSpec.load(self._path(item.problem))
            problem = self.renderer.formatted_problem(
                self._path(item.problem), self._path(item.public_tests))
            calls.extend(self._dry_problem_calls(spec.problem_id, problem))
        plan = {"run_id": run_id, "mode": "dry-run", "model_calls": calls,
                "api_accessed": False, "judge_accessed": False}
        write_json(self.run_dir / "dry_run_plan.json", plan)
        return plan

    def _dry_problem_calls(self, problem_id: str, problem: str) -> list[dict[str, Any]]:
        calls = [self._rendered_call("teacher", problem_id, "teacher", problem)]
        # Show every possible branch without using prior model output.
        calls.append(self._rendered_call("success_teaching", problem_id, "success", problem,
                                         teacher_raw_response="<teacher-response>",
                                         teacher_code="<teacher-code>"))
        calls.append(self._rendered_call("failure_frontier", problem_id, "failure", problem,
                                         teacher_raw_response="<teacher-response>",
                                         teacher_code="<teacher-code>", teacher_verdict="<coarse-verdict>"))
        guidance = self._rendered_call(
            "general_guidance", problem_id, "initial", problem,
            target_tokens="<failure-frontier-output-tokens>",
            lower_bound="<lower-bound>",
            upper_bound="<upper-bound>",
        )
        guidance["max_output_tokens"] = "<upper-bound-plus-headroom>"
        calls.append(guidance)
        for condition in STUDENT_CONDITIONS:
            calls.append(self._rendered_call("student", problem_id, condition, problem,
                                             additional_material="<condition-specific-material>"))
        return calls

    def _run_problem(self, run_id: str, item: ProblemConfig) -> dict[str, Any]:
        assert self.run_dir is not None
        spec = ProblemSpec.load(self._path(item.problem))
        problem = self.renderer.formatted_problem(
            self._path(item.problem), self._path(item.public_tests))
        problem_dir = self.run_dir / "problems" / spec.problem_id
        record_path = problem_dir / "record.json"
        if self.config.execution.resume and record_path.is_file():
            saved_record = read_json(record_path)
            if not saved_record.get("infrastructure_error"):
                return saved_record
        record: dict[str, Any] = {
            "run_id": run_id,
            "problem_id": spec.problem_id,
            "teacher": {},
            "teaching_material": {
                "type": None,
                "success_tokens": None,
                "failure_frontier_tokens": None,
                "general_guidance_tokens": None,
                "token_relative_error": None,
                "token_match_passed": None,
                "token_match_failed": None,
            },
            "students": {},
            "valid_episode": True,
            "condition_comparison_eligible": True,
            "artifacts": {},
        }
        try:
            teacher = self._solver_stage(
                problem_dir / "teacher", "teacher", spec.problem_id, "teacher",
                problem, item, spec,
            )
            record["teacher"] = _solver_summary(teacher)
            record["artifacts"]["teacher"] = teacher["artifact_paths"]
            if teacher["verdict"] == "JUDGE_ERROR":
                record["valid_episode"] = False
                record["infrastructure_error"] = "judge"
                write_json(record_path, record)
                return record
            if teacher["verdict"] == "AC":
                material = self._success_material(problem_dir, spec.problem_id, problem, teacher)
                record["teaching_material"].update({
                    "type": "success",
                    "success_tokens": material.output_tokens,
                    "success_truncated": material.truncated,
                })
                record["artifacts"]["teaching_materials"] = str(
                    problem_dir / "teaching_materials")
                student_materials = {condition: material.content for condition in STUDENT_CONDITIONS}
            else:
                ff = self._failure_material(problem_dir, spec.problem_id, problem, teacher)
                record["teaching_material"].update({
                    "type": "failure",
                    "failure_frontier_tokens": ff.output_tokens,
                    "failure_frontier_truncated": ff.truncated,
                })
                gg = self._matched_guidance(problem_dir, spec.problem_id, problem, ff.output_tokens)
                record["teaching_material"].update(gg["metrics"])
                record["artifacts"]["teaching_materials"] = str(
                    problem_dir / "teaching_materials")
                if not gg["metrics"]["token_match_passed"]:
                    record["token_match_failed"] = True
                    record["condition_comparison_eligible"] = False
                student_materials = {
                    "success_only": "",
                    "failure_frontier": ff.content,
                    "general_guidance": gg["response"].content,
                }
            for condition in STUDENT_CONDITIONS:
                student = self._solver_stage(
                    problem_dir / f"student_{condition}", "student", spec.problem_id,
                    condition, problem, item, spec,
                    additional_material=student_materials[condition],
                    success_branch=teacher["verdict"] == "AC",
                )
                record["students"][condition] = _solver_summary(student)
                record["artifacts"][f"student_{condition}"] = student["artifact_paths"]
        except ModelInfrastructureError:
            record["valid_episode"] = False
            record["infrastructure_error"] = "model_api"
        write_json(record_path, record)
        return record

    def _solver_stage(
        self, stage_dir: Path, role: str, problem_id: str, condition: str,
        problem: str, item: ProblemConfig, spec: ProblemSpec, *,
        additional_material: str = "", success_branch: bool = False,
    ) -> dict[str, Any]:
        state_path = stage_dir / "state.json"
        if self.config.execution.resume and state_path.is_file():
            state = read_json(state_path)
            if (state.get("status") == "completed" and
                    state.get("result", {}).get("verdict") != "JUDGE_ERROR"):
                return state["result"]
        rendered = self._rendered_call(
            role, problem_id, condition, problem,
            additional_material=additional_material,
            success_branch=success_branch,
        )
        response, call_path = self._call(stage_dir, role, problem_id, condition, rendered)
        extraction = extract_single_python_code(response.content,
                                                 truncated=response.truncated)
        submission_path = stage_dir / "submission.py"
        judge_path = stage_dir / "judge.internal.json"
        if not extraction.ok:
            verdict = "CE"
            judge_record = {
                "submitted": False,
                "failure_type": "OUTPUT_FORMAT_ERROR",
                "extraction_error": extraction.error,
            }
        else:
            write_text(submission_path, extraction.code or "")
            try:
                internal: JudgeResult = self.judge.judge(
                    submission_path,
                    self._path(item.problem),
                    self._path(item.hidden_tests),
                    phase=self.config.execution.judge_phase,
                )
                verdict = coarse_verdict(internal.verdict)
                judge_record = {
                    "submitted": True,
                    "verdict": verdict,
                    "internal_result": internal.to_dict(),
                    "runtime_ms": internal.runtime_ms,
                    "memory_limit_mb": spec.limits.memory_mb,
                    "peak_memory_mb": None,
                    "internal_sandbox_log_path": str(judge_path),
                    "infrastructure_error": verdict == "JUDGE_ERROR",
                }
            except (DockerUnavailableError, OSError, ValueError) as error:
                verdict = "JUDGE_ERROR"
                judge_record = {
                    "submitted": True,
                    "verdict": verdict,
                    "infrastructure_error": True,
                    "error_category": type(error).__name__,
                }
        write_json(judge_path, judge_record)
        result = {
            "verdict": verdict,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "truncated": response.truncated,
            "format_error": extraction.error,
            "artifact_paths": {
                "model_call": str(call_path),
                "submission": str(submission_path) if extraction.ok else None,
                "judge_internal": str(judge_path),
            },
            "raw_response": response.content,
            "code": extraction.code,
        }
        write_json(state_path, {"status": "completed", "completed_at": _now(),
                                "result": result})
        return result

    def _success_material(self, problem_dir: Path, problem_id: str, problem: str,
                          teacher: dict[str, Any]) -> ModelResponse:
        rendered = self._rendered_call(
            "success_teaching", problem_id, "success", problem,
            teacher_raw_response=teacher["raw_response"],
            teacher_code=teacher["code"],
        )
        return self._call(problem_dir / "teaching_materials" / "success",
                          "success_teaching", problem_id, "success", rendered)[0]

    def _failure_material(self, problem_dir: Path, problem_id: str, problem: str,
                          teacher: dict[str, Any]) -> ModelResponse:
        rendered = self._rendered_call(
            "failure_frontier", problem_id, "failure", problem,
            teacher_raw_response=teacher["raw_response"],
            teacher_code=teacher["code"] or "<no extractable code>",
            teacher_verdict=teacher["verdict"],
        )
        return self._call(problem_dir / "teaching_materials" / "failure_frontier",
                          "failure_frontier", problem_id, "failure", rendered)[0]

    def _matched_guidance(self, problem_dir: Path, problem_id: str, problem: str,
                          target_tokens: int | None) -> dict[str, Any]:
        if target_tokens is None or target_tokens <= 0:
            raise ModelInfrastructureError(
                "reliable Failure Frontier completion token usage is required"
            )
        teaching = self.config.teaching_material
        lower_bound, upper_bound = guidance_token_bounds(
            target_tokens, teaching.token_match_tolerance
        )
        dynamic_max_tokens = max(
            teaching.gg_min_max_tokens,
            upper_bound + teaching.gg_token_headroom,
        )
        stage_root = problem_dir / "teaching_materials" / "general_guidance"
        responses: list[ModelResponse] = []
        version_records: list[dict[str, Any]] = []
        matched_version: int | None = None
        stop_reason = "maximum_adjustments_reached"

        for version in range(teaching.max_regeneration_attempts + 1):
            if version == 0:
                operation = "initial"
                input_version = None
                role = "general_guidance"
                condition = "initial"
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                )
            else:
                previous = responses[-1]
                assert previous.output_tokens is not None
                direction = (
                    "compress" if previous.output_tokens >= target_tokens
                    else "expand"
                )
                operation = direction
                input_version = version - 1
                role = "general_guidance_adjust"
                condition = f"{direction}_{version}"
                retain = target_tokens / previous.output_tokens * 100
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    current_tokens=previous.output_tokens,
                    retain_ratio_percent=f"{retain:.1f}",
                    remove_ratio_percent=f"{max(0.0, 100 - retain):.1f}",
                    expand_ratio_percent=f"{max(0.0, retain - 100):.1f}",
                    general_guidance=previous.content,
                    direction=direction,
                )

            version_dir = stage_root / f"version_{version}"
            response = self._call(
                version_dir, role, problem_id, condition, rendered,
                max_output_tokens=dynamic_max_tokens,
            )[0]
            if response.token_count_source not in {"api_usage", "mock_usage"}:
                raise ModelInfrastructureError(
                    "General Guidance requires API completion_tokens; tokenizer fallback is not accepted"
                )
            responses.append(response)
            content_path = version_dir / "content.md"
            write_text(content_path, response.content)
            valid_content, structural_errors = validate_guidance_content(
                response.content
            )
            status = guidance_candidate_status(
                response, lower_bound, upper_bound, valid_content
            )
            record = guidance_version_record(
                version=version,
                operation=operation,
                input_version=input_version,
                response=response,
                content_path=content_path,
                target_tokens=target_tokens,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                dynamic_max_tokens=dynamic_max_tokens,
                status=status,
                valid_content=valid_content,
                structural_errors=structural_errors,
            )
            version_records.append(record)
            write_json(version_dir / "version.json", record)

            if record["matched"]:
                matched_version = version
                stop_reason = "first_valid_candidate_in_interval"
                break
            if not response.content.strip():
                stop_reason = "empty_content"
                break

        valid_records = [item for item in version_records if item["valid_candidate"]]
        if matched_version is not None:
            selected_version = matched_version
            selection_reason = "first_valid_candidate_in_interval"
            passed = True
        elif valid_records:
            selected = min(
                valid_records,
                key=lambda item: (
                    item["distance_to_target"],
                    item["distance_to_interval"],
                    item["version"],
                ),
            )
            selected_version = selected["version"]
            selection_reason = "closest_valid_candidate_for_audit"
            passed = False
        else:
            selected_version = None
            selection_reason = "no_valid_candidate"
            passed = False

        match_record = {
            "target_tokens": target_tokens,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "dynamic_max_tokens": dynamic_max_tokens,
            "max_regeneration_attempts": teaching.max_regeneration_attempts,
            "attempts_used": len(version_records),
            "matched_version": matched_version,
            "selected_version": selected_version,
            "selection_reason": selection_reason,
            "stop_reason": stop_reason,
            "token_match_passed": passed,
            "token_match_failed": not passed,
            "versions": version_records,
        }
        write_json(stage_root / "match.json", match_record)
        if selected_version is None:
            raise ModelInfrastructureError(
                "General Guidance produced no complete structurally valid candidate"
            )
        response = responses[selected_version]
        error = token_relative_error(target_tokens, response.output_tokens)
        return {
            "response": response,
            "metrics": {
                "target_tokens": target_tokens,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "dynamic_max_tokens": dynamic_max_tokens,
                "attempts_used": len(version_records),
                "matched_version": matched_version,
                "selected_version": selected_version,
                "selection_reason": selection_reason,
                "general_guidance_tokens": response.output_tokens,
                "token_relative_error": error,
                "token_match_passed": passed,
                "token_match_failed": not passed,
                "general_guidance_truncated": response.truncated,
            },
        }

    def _rendered_call(self, role: str, problem_id: str, condition: str,
                       problem: str, **values: Any) -> dict[str, str]:
        if role == "teacher":
            system = self.renderer.template("teacher.md")
            user = problem
        elif role == "success_teaching":
            system = self.renderer.template("success_teaching.md")
            user = self.renderer.render(
                self.renderer.template("success_teaching_user.md"),
                formatted_problem=problem,
                teacher_raw_response=values["teacher_raw_response"],
                teacher_code=values["teacher_code"],
            )
        elif role == "failure_frontier":
            system = self.renderer.template("failure_frontier.md")
            user = self.renderer.render(
                self.renderer.template("failure_frontier_user.md"),
                formatted_problem=problem,
                teacher_raw_response=values["teacher_raw_response"],
                teacher_code=values["teacher_code"],
                teacher_verdict=values["teacher_verdict"],
            )
        elif role == "general_guidance":
            system = self.renderer.render(
                self.renderer.template("general_guidance.md"),
                target_tokens=values["target_tokens"],
                lower_bound=values["lower_bound"],
                upper_bound=values["upper_bound"],
            )
            user = problem
        elif role == "general_guidance_adjust":
            system = self.renderer.render(
                self.renderer.template(f"general_guidance_{values['direction']}.md"),
                target_tokens=values["target_tokens"],
                lower_bound=values["lower_bound"],
                upper_bound=values["upper_bound"],
                current_tokens=values["current_tokens"],
                retain_ratio_percent=values["retain_ratio_percent"],
                remove_ratio_percent=values["remove_ratio_percent"],
                expand_ratio_percent=values["expand_ratio_percent"],
            )
            user = self.renderer.render(
                self.renderer.template("general_guidance_adjust_user.md"),
                formatted_problem=problem,
                general_guidance=values["general_guidance"],
            )
        elif role == "student":
            system = self.renderer.template("student.md")
            material = values.get("additional_material", "")
            if condition == "success_only" and not values.get("success_branch"):
                user = problem
            else:
                user = self.renderer.render(
                    self.renderer.template("student_user_with_material.md"),
                    formatted_problem=problem,
                    additional_material=material,
                )
        else:
            raise ValueError(f"unsupported role: {role}")
        return {"role": role, "problem_id": problem_id, "condition": condition,
                "system_prompt": system, "user_prompt": user}

    def _call(self, stage_dir: Path, role: str, problem_id: str, condition: str,
              rendered: dict[str, str], *,
              max_output_tokens: int | None = None) -> tuple[ModelResponse, Path]:
        artifact = stage_dir / "model_call.json"
        effective_max_tokens = (
            self.config.model.max_output_tokens
            if max_output_tokens is None else max_output_tokens
        )
        if self.config.execution.resume and artifact.is_file():
            saved = read_json(artifact)
            if saved.get("status") == "completed":
                if saved.get("model", {}).get("max_output_tokens") != effective_max_tokens:
                    raise ModelInfrastructureError(
                        "persisted model call max_output_tokens differs from current request"
                    )
                return ModelResponse(**saved["response"]), artifact
        assert self.model is not None
        response = self.model.complete(
            **rendered, max_output_tokens=effective_max_tokens
        )
        payload = {
            "status": "completed",
            "role": role,
            "problem_id": problem_id,
            "condition": condition,
            "system_prompt": rendered["system_prompt"],
            "user_prompt": rendered["user_prompt"],
            "response": asdict(response),
            "model": {
                "provider": self.config.model.provider,
                "model_name": self.config.model.model_name,
                "reasoning_mode": self.config.model.reasoning_mode,
                "temperature": self.config.model.temperature,
                "top_p": self.config.model.top_p,
                "max_output_tokens": effective_max_tokens,
                "configured_solver_max_output_tokens": self.config.model.max_output_tokens,
            },
            "prompt_hash": _hash(rendered["system_prompt"] + "\0" + rendered["user_prompt"]),
            "completed_at": _now(),
        }
        write_json(artifact, payload)
        write_json(stage_dir / "call.state.json", {
            "status": "completed",
            "artifact": str(artifact),
            "completed_at": payload["completed_at"],
        })
        if (response.reasoning_content not in (None, "") or
                type(response.input_tokens) is not int or response.input_tokens < 0 or
                type(response.output_tokens) is not int or response.output_tokens <= 0 or
                type(response.total_tokens) is not int or response.total_tokens <= 0):
            raise ModelInfrastructureError(
                "model response failed non-reasoning or API usage validation")
        return response, artifact


def token_relative_error(target: int, actual: int | None) -> float | None:
    if target <= 0 or actual is None:
        return None
    return abs(actual - target) / target


def guidance_token_bounds(target: int, tolerance: float) -> tuple[int, int]:
    if target <= 0 or not 0 <= tolerance < 1:
        raise ValueError("target and token tolerance must define a positive interval")
    return (
        math.ceil(target * (1 - tolerance)),
        math.floor(target * (1 + tolerance)),
    )


def guidance_distance_to_interval(actual: int, lower: int, upper: int) -> int:
    if actual < lower:
        return lower - actual
    if actual > upper:
        return actual - upper
    return 0


def validate_guidance_content(content: str) -> tuple[bool, list[str]]:
    text = content.strip()
    errors: list[str] = []
    if not text:
        return False, ["empty_content"]
    positions = [text.find(section) for section in GG_REQUIRED_SECTIONS]
    if any(position < 0 for position in positions):
        errors.append("missing_required_section")
    elif positions != sorted(positions) or len(set(positions)) != len(positions):
        errors.append("required_sections_out_of_order")
    else:
        for index, position in enumerate(positions):
            body_start = position + len(GG_REQUIRED_SECTIONS[index])
            body_end = positions[index + 1] if index + 1 < len(positions) else len(text)
            if not text[body_start:body_end].strip():
                errors.append(f"empty_section_{index}")
    if "```" in text:
        errors.append("code_fence_not_allowed")
    last_line = text.splitlines()[-1].strip()
    if (last_line.startswith("#") or last_line in {"-", "*", "+"} or
            last_line.endswith((":", ",", ";", "-", "(", "["))):
        errors.append("obviously_incomplete_ending")
    return not errors, errors


def guidance_candidate_status(
    response: ModelResponse,
    lower_bound: int,
    upper_bound: int,
    valid_content: bool,
) -> str:
    if response.finish_reason != "stop":
        return "INVALID_FINISH_REASON"
    if not valid_content:
        return "INVALID_CONTENT"
    if response.output_tokens is None:
        raise ModelInfrastructureError(
            "reliable General Guidance completion token usage is required"
        )
    if response.output_tokens < lower_bound:
        return "TOO_SHORT"
    if response.output_tokens > upper_bound:
        return "TOO_LONG"
    return "MATCHED"


def guidance_version_record(
    *,
    version: int,
    operation: str,
    input_version: int | None,
    response: ModelResponse,
    content_path: Path,
    target_tokens: int,
    lower_bound: int,
    upper_bound: int,
    dynamic_max_tokens: int,
    status: str,
    valid_content: bool,
    structural_errors: list[str],
) -> dict[str, Any]:
    if response.output_tokens is None:
        raise ModelInfrastructureError(
            "reliable General Guidance completion token usage is required"
        )
    tokens = response.output_tokens
    valid_candidate = response.finish_reason == "stop" and valid_content
    return {
        "version": version,
        "operation": operation,
        "input_version": input_version,
        "prompt_tokens": response.input_tokens,
        "completion_tokens": tokens,
        "total_tokens": response.total_tokens,
        "finish_reason": response.finish_reason,
        "response_id": response.response_id,
        "content_path": str(content_path),
        "relative_error": token_relative_error(target_tokens, tokens),
        "distance_to_target": abs(tokens - target_tokens),
        "distance_to_interval": guidance_distance_to_interval(
            tokens, lower_bound, upper_bound
        ),
        "matched": status == "MATCHED",
        "valid_candidate": valid_candidate,
        "status": status,
        "structural_errors": structural_errors,
        "dynamic_max_tokens": dynamic_max_tokens,
    }


def _solver_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result[key] for key in (
        "verdict", "input_tokens", "output_tokens", "truncated", "format_error"
    )}


def build_summary(run_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [record for record in records if record.get("valid_episode")]
    comparable = [
        record for record in valid
        if record.get("condition_comparison_eligible", True)
    ]
    teacher_failures = [record for record in comparable
                        if record.get("teacher", {}).get("verdict") != "AC"]
    all_teacher_failures = [record for record in valid
                            if record.get("teacher", {}).get("verdict") != "AC"]
    conditions = STUDENT_CONDITIONS
    summary: dict[str, Any] = {
        "run_id": run_id,
        "pilot_only": True,
        "interpretation": "Execution-chain pilot; not a statistical significance result.",
        "problem_count": len(records),
        "valid_episode_count": len(valid),
        "invalid_episode_count": len(records) - len(valid),
        "condition_comparison_eligible_count": len(comparable),
        "condition_comparison_ineligible_count": len(valid) - len(comparable),
        "teacher_ac_count": sum(
            r.get("teacher", {}).get("verdict") == "AC" for r in comparable
        ),
        "teacher_failure_count": len(teacher_failures),
        "student_ac_count": {},
        "student_breakthrough_on_teacher_failures": {},
        "baseline_fail_gg_fail_ff_success": [],
        "baseline_fail_ff_fail_gg_success": [],
        "truncated_call_count": 0,
        "token_matching": {},
    }
    for condition in conditions:
        summary["student_ac_count"][condition] = sum(
            r.get("students", {}).get(condition, {}).get("verdict") == "AC"
            for r in comparable
        )
        summary["student_breakthrough_on_teacher_failures"][condition] = sum(
            r.get("students", {}).get(condition, {}).get("verdict") == "AC"
            for r in teacher_failures)
    for record in teacher_failures:
        students = record.get("students", {})
        baseline = students.get("success_only", {}).get("verdict")
        ff = students.get("failure_frontier", {}).get("verdict")
        gg = students.get("general_guidance", {}).get("verdict")
        if baseline != "AC" and gg != "AC" and ff == "AC":
            summary["baseline_fail_gg_fail_ff_success"].append(record["problem_id"])
        if baseline != "AC" and ff != "AC" and gg == "AC":
            summary["baseline_fail_ff_fail_gg_success"].append(record["problem_id"])
    calls = [record.get("teacher", {}) for record in records]
    calls += [student for record in records for student in record.get("students", {}).values()]
    material_truncations = []
    for record in records:
        material = record.get("teaching_material", {})
        material_truncations.extend(
            bool(material.get(key)) for key in (
                "success_truncated", "failure_frontier_truncated",
                "general_guidance_truncated"
            )
        )
    summary["truncated_call_count"] = (
        sum(bool(call.get("truncated")) for call in calls) +
        sum(material_truncations)
    )
    failed_materials = [
        record["teaching_material"] for record in all_teacher_failures
    ]
    paired = [item for item in failed_materials
              if item.get("failure_frontier_tokens") is not None and
              item.get("general_guidance_tokens") is not None]
    summary["token_matching"] = {
        "pair_count": len(paired),
        "average_failure_frontier_tokens": _average(
            [item["failure_frontier_tokens"] for item in paired]),
        "average_general_guidance_tokens": _average(
            [item["general_guidance_tokens"] for item in paired]),
        "average_relative_error": _average(
            [item["token_relative_error"] for item in paired
             if item.get("token_relative_error") is not None]),
        "failed_count": sum(item.get("token_match_passed") is False for item in paired),
    }
    return summary


def summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Failure-Frontier Teaching Pilot Summary",
        "",
        "This is an execution-chain pilot for preliminary signals only; it does not support statistical significance claims.",
        "",
        f"- Problems: {summary['problem_count']}",
        f"- Valid episodes: {summary['valid_episode_count']}",
        f"- Invalid episodes: {summary['invalid_episode_count']}",
        f"- Condition-comparison eligible: {summary['condition_comparison_eligible_count']}",
        f"- Condition-comparison ineligible: {summary['condition_comparison_ineligible_count']}",
        f"- Teacher AC: {summary['teacher_ac_count']}",
        f"- Teacher failures: {summary['teacher_failure_count']}",
        "",
        "## Student AC counts",
        "",
    ]
    for condition, count in summary["student_ac_count"].items():
        lines.append(f"- {condition}: {count}")
    lines.extend(["", "## Breakthroughs on Teacher failures", ""])
    for condition, count in summary["student_breakthrough_on_teacher_failures"].items():
        lines.append(f"- {condition}: {count}")
    return "\n".join(lines) + "\n"


def _average(values: list[float | int]) -> float | None:
    return sum(values) / len(values) if values else None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def smoke_markdown(result: dict[str, Any]) -> str:
    record = result["record"]
    lines = [
        "# Informal Single-Problem Smoke Test",
        "",
        "This artifact is not part of the formal five-problem Pilot.",
        "",
        f"- Problem: {result['problem_id']}",
        f"- Passed: {result['passed']}",
        f"- Teacher verdict: {record.get('teacher', {}).get('verdict')}",
        f"- Valid episode: {record.get('valid_episode')}",
        "",
        "## Audit",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in result["audit"].items())
    return "\n".join(lines) + "\n"
