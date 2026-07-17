from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import math
import os
import re
import subprocess
import sys

from ffjudge.models import JudgeResult, ProblemSpec, Verdict
from ffjudge.runner import DockerJudge, DockerUnavailableError

from .code_extraction import extract_fenced_python_submission
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
    "## Algorithmic Directions",
    "## Correctness and Edge Cases",
    "## Implementation Checks",
)
GG_CATEGORIES = ("constraints", "approaches", "correctness", "implementation")
GG_SECTION_ALIASES = {
    "constraints": {
        "constraint analysis", "constraints and observations", "key constraints",
        "constraints", "problem constraints",
    },
    "approaches": {
        "plausible approaches", "possible approaches", "possible algorithms",
        "algorithmic approach", "algorithmic directions", "candidate approaches",
        "solution directions",
    },
    "correctness": {
        "edge cases and correctness", "correctness and edge cases",
        "correctness pitfalls and edge cases", "edge cases",
        "correctness considerations", "validation considerations",
    },
    "implementation": {
        "implementation checks", "implementation considerations",
        "implementation risks", "implementation notes", "coding considerations",
        "complexity and implementation",
    },
}
GG_CATEGORY_SIGNALS = {
    "constraints": (
        r"\bconstraints?\b", r"\binput size\b", r"\btime complexity\b",
        r"\bspace complexity\b", r"\bupper bound\b", r"\blower bound\b",
        r"\bO\s*\([^\n)]*\)",
    ),
    "approaches": (
        r"\balgorithms?\b", r"\bapproach(?:es)?\b", r"\bdynamic programming\b",
        r"\bgreedy\b", r"\bbinary search\b", r"\bdata structure\b",
        r"\brecurrence\b", r"\bstate transition\b", r"\bcandidate direction\b",
    ),
    "correctness": (
        r"\bcorrectness\b", r"\bproof\b", r"\binvariant\b", r"\bedge cases?\b",
        r"\bboundar(?:y|ies)\b", r"\bdegenerate\b", r"\bimpossible\b",
        r"\bwhy\b", r"\bpitfalls?\b",
    ),
    "implementation": (
        r"\bimplementation\b", r"\bcoding\b", r"\boff-by-one\b",
        r"\boverflow\b", r"\bindex(?:ing)?\b", r"\bmemory\b",
        r"\bdata types?\b", r"\btests?\b", r"\brisks?\b", r"\bchecks?\b",
    ),
}


class GGContentValidationError(RuntimeError):
    """A successful model response that violates the GG content protocol."""

    def __init__(self, message: str, *, validation_error: str) -> None:
        super().__init__(message)
        self.validation_error = validation_error


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
        teacher_planning = [call for call in calls
                            if call.get("role") == "teacher_planning"]
        teacher_final = [call for call in calls
                         if call.get("role") == "teacher_final"]
        expected_problem = self.renderer.formatted_problem(
            self._path(item.problem), self._path(item.public_tests))
        teacher_public_only = (
            len(teacher_planning) == 1 and len(teacher_final) == 1 and
            teacher_planning[0].get("user_prompt") == expected_problem and
            teacher_final[0].get("user_prompt", "").startswith(expected_problem) and
            "# Additional Material" not in teacher_final[0].get("user_prompt", "")
        )
        baseline_planning = [call for call in calls
                             if call.get("role") == "student_planning" and
                             call.get("condition") == "success_only"]
        baseline_final = [call for call in calls
                          if call.get("role") == "student_final" and
                          call.get("condition") == "success_only"]
        baseline_exact = bool(baseline_planning and baseline_final) and (
            record.get("teacher", {}).get("verdict") == "AC" or
            (baseline_planning[0].get("user_prompt") == expected_problem and
             baseline_final[0].get("user_prompt", "").startswith(expected_problem) and
             "# Additional Material" not in baseline_final[0].get("user_prompt", ""))
        )
        ff_calls = [call for call in calls if call.get("role") == "student_final" and
                    call.get("condition") == "failure_frontier"]
        gg_calls = [call for call in calls if call.get("role") == "student_final" and
                    call.get("condition") == "general_guidance"]
        student_system_equal = bool(ff_calls and gg_calls) and (
            ff_calls[0].get("system_prompt") == gg_calls[0].get("system_prompt"))
        student_planning = [call for call in calls
                            if call.get("role") == "student_planning"]
        student_final = [call for call in calls
                         if call.get("role") == "student_final"]
        success_student_prompts_equal = True
        if record.get("teacher", {}).get("verdict") == "AC":
            success_student_prompts_equal = (
                len(student_planning) == 3 and len(student_final) == 3 and
                len({call.get("system_prompt") for call in student_planning}) == 1 and
                len({call.get("user_prompt") for call in student_planning}) == 1 and
                len({call.get("system_prompt") for call in student_final}) == 1
            )
        sentinel_ff = self._rendered_solver_call(
            "planning", "student", record["problem_id"], "failure_frontier",
            expected_problem,
            additional_material="FF_MATERIAL_SENTINEL", success_branch=False)
        sentinel_gg = self._rendered_solver_call(
            "planning", "student", record["problem_id"], "general_guidance",
            expected_problem,
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
            "teacher_called_once": len(teacher_planning) == 1 and len(teacher_final) == 1,
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
        calls = [
            self._rendered_solver_call("planning", "teacher", problem_id, "teacher", problem),
            self._rendered_solver_call(
                "final", "teacher", problem_id, "teacher", problem,
                planning_content="<teacher-planning>", planning_status="<planning-status>"
            ),
        ]
        # Show every possible branch without using prior model output.
        calls.append(self._rendered_call("success_teaching", problem_id, "success", problem,
                                         teacher_planning="<teacher-planning>",
                                         teacher_raw_response="<teacher-response>",
                                         teacher_code="<teacher-code>"))
        calls.append(self._rendered_call("failure_frontier", problem_id, "failure", problem,
                                         teacher_planning="<teacher-planning>",
                                         teacher_raw_response="<teacher-response>",
                                         teacher_code="<teacher-code>", teacher_verdict="<coarse-verdict>"))
        guidance = self._rendered_call(
            "general_guidance", problem_id, "initial", problem,
            target_tokens="<failure-frontier-output-tokens>",
            lower_bound="<lower-bound>",
            upper_bound="<upper-bound>",
        )
        guidance["max_output_tokens"] = self.config.teaching_material.gg_max_output_tokens
        calls.append(guidance)
        for condition in STUDENT_CONDITIONS:
            for stage in ("planning", "final"):
                calls.append(self._rendered_solver_call(
                    stage, "student", problem_id, condition, problem,
                    additional_material="<condition-specific-material>",
                    planning_content="<role-planning>",
                    planning_status="<planning-status>",
                ))
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
                saved_record["condition_comparison_eligible"] = (
                    condition_comparison_eligible(saved_record)
                )
                write_json(record_path, saved_record)
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
            "condition_comparison_eligible": None,
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
                record["condition_comparison_eligible"] = (
                    condition_comparison_eligible(record)
                )
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
        except GGContentValidationError as error:
            record["valid_episode"] = False
            record["model_output_validation"] = "gg_content_validation"
            record["protocol_output_invalid"] = True
            record["validation_error"] = error.validation_error
        except ModelInfrastructureError:
            record["valid_episode"] = False
            record["infrastructure_error"] = "model_api"
        record["condition_comparison_eligible"] = condition_comparison_eligible(record)
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
        submission_record = stage_dir / "submission.json"
        if self.config.execution.resume and submission_record.is_file():
            saved_submission = read_json(submission_record)
            if (saved_submission.get("status") == "completed" and
                    saved_submission.get("result", {}).get("verdict") !=
                    "JUDGE_ERROR"):
                result = saved_submission["result"]
                write_json(state_path, {"status": "completed", "completed_at": _now(),
                                        "result": result})
                return result

        solver = self.config.solver
        planning_rendered = self._rendered_solver_call(
            "planning", role, problem_id, condition, problem,
            additional_material=additional_material, success_branch=success_branch,
        )
        planning, planning_call = self._call(
            stage_dir / "planning", f"{role}_planning", problem_id, condition,
            planning_rendered, max_output_tokens=solver.planning_max_output_tokens,
        )
        planning_warnings = _planning_warnings(planning)
        write_text(stage_dir / "planning" / "content.md", planning.content)
        write_json(stage_dir / "planning" / "stage.json", _stage_metadata(
            "planning", solver.planning_max_output_tokens, planning,
            planning_call, planning_warnings,
        ))
        if not planning.content.strip():
            planning_status = (
                "The planning output was empty or unusable. Solve the problem using "
                "the original task information and submit the best complete solution "
                "without further open-ended brainstorming."
            )
            planning_content = "<planning unavailable>"
        elif planning.truncated:
            planning_status = (
                "The planning phase reached its fixed output budget and may be "
                "incomplete. Do not continue the exploration. Use the best available "
                "direction and submit one complete solution."
            )
            planning_content = planning.content
        else:
            planning_status = (
                "The planning phase completed. Do not continue exploration; use the "
                "best available direction and submit one complete solution."
            )
            planning_content = planning.content

        final_rendered = self._rendered_solver_call(
            "final", role, problem_id, condition, problem,
            additional_material=additional_material, success_branch=success_branch,
            planning_content=planning_content, planning_status=planning_status,
        )
        response, call_path = self._call(
            stage_dir / "final", f"{role}_final", problem_id, condition,
            final_rendered, max_output_tokens=solver.final_max_output_tokens,
        )
        write_text(stage_dir / "final" / "content.md", response.content)
        extraction = extract_fenced_python_submission(response.content)
        final_warnings = [] if extraction.ok else [
            f"final_output_validation:{extraction.error}"
        ]
        write_json(stage_dir / "final" / "stage.json", _stage_metadata(
            "final", solver.final_max_output_tokens, response, call_path,
            final_warnings,
        ))
        submission_path = stage_dir / "final" / "extracted_solution.py"
        judge_path = stage_dir / "judge.internal.json"
        judge_submissions = 0
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
                judge_submissions = 1
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
                "planning_model_call": str(planning_call),
                "planning_content": str(stage_dir / "planning" / "content.md"),
                "planning_stage": str(stage_dir / "planning" / "stage.json"),
                "final_model_call": str(call_path),
                "final_content": str(stage_dir / "final" / "content.md"),
                "final_stage": str(stage_dir / "final" / "stage.json"),
                "submission_record": str(submission_record),
            },
            "raw_response": response.content,
            "code": extraction.code,
            "planning_response": planning.content,
            "solver_protocol": solver.protocol,
            "planning_calls": 1,
            "final_calls": 1,
            "judge_submissions": judge_submissions,
            "planning_truncated": planning.truncated,
            "final_truncated": response.truncated,
            "final_code_extracted": extraction.ok,
            "final_verdict": verdict,
            "planning_validation_warnings": planning_warnings,
            "output_failure_category": (
                None if extraction.ok else "final_output_validation"
            ),
        }
        write_json(submission_record, {"status": "completed", "result": result})
        write_json(state_path, {"status": "completed", "completed_at": _now(),
                                "result": result})
        return result

    def _success_material(self, problem_dir: Path, problem_id: str, problem: str,
                          teacher: dict[str, Any]) -> ModelResponse:
        rendered = self._rendered_call(
            "success_teaching", problem_id, "success", problem,
            teacher_planning=teacher["planning_response"],
            teacher_raw_response=teacher["raw_response"],
            teacher_code=teacher["code"],
        )
        return self._call(problem_dir / "teaching_materials" / "success",
                          "success_teaching", problem_id, "success", rendered)[0]

    def _failure_material(self, problem_dir: Path, problem_id: str, problem: str,
                          teacher: dict[str, Any]) -> ModelResponse:
        rendered = self._rendered_call(
            "failure_frontier", problem_id, "failure", problem,
            teacher_planning=teacher["planning_response"],
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
        gg_max_output_tokens = teaching.gg_max_output_tokens
        stage_root = problem_dir / "teaching_materials" / "general_guidance"
        responses: list[ModelResponse] = []
        version_records: list[dict[str, Any]] = []
        matched_version: int | None = None
        stop_reason = "maximum_adjustments_reached"

        for version in range(teaching.max_regeneration_attempts + 1):
            anchors = guidance_anchor_records(version_records)
            long_anchor = anchors["long"]
            short_anchor = anchors["short"]
            source_version: int | None = None
            retain_ratio: float | None = None
            remove_ratio: float | None = None
            expand_ratio: float | None = None
            ratio_strategy: str | None = None
            feedback_source_version: int | None = None
            revision_feedback: str | None = None
            if version == 0:
                operation = "initial"
                source_reason = "initial_generation"
                role = "general_guidance"
                condition = "initial"
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                )
            elif long_anchor is not None:
                operation = "compress"
                source_version = long_anchor["version"]
                source_reason = "compress_best_complete_long_candidate"
                role = "general_guidance_adjust"
                condition = f"compress_{version}"
                previous_compression = guidance_latest_compression(
                    version_records, long_anchor["version"]
                )
                retain_ratio, ratio_strategy = guidance_retain_ratio(
                    target_tokens, long_anchor, short_anchor,
                    previous_compression=previous_compression,
                )
                remove_ratio = 1.0 - retain_ratio
                if previous_compression is not None:
                    feedback_source_version = previous_compression["version"]
                    revision_feedback = guidance_compression_feedback(
                        previous_compression, lower_bound, upper_bound
                    )
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    source_tokens=long_anchor["completion_tokens"],
                    retain_ratio_percent=f"{retain_ratio * 100:.1f}",
                    remove_ratio_percent=f"{remove_ratio * 100:.1f}",
                    expand_ratio_percent="0.0",
                    general_guidance=responses[source_version].content,
                    revision_feedback=revision_feedback or "",
                    direction="compress",
                )
            elif short_anchor is not None:
                operation = "expand"
                source_version = short_anchor["version"]
                source_reason = "expand_best_complete_short_without_long_candidate"
                role = "general_guidance_adjust"
                condition = f"expand_{version}"
                expand_ratio = max(
                    0.0,
                    target_tokens / short_anchor["completion_tokens"] - 1.0,
                )
                ratio_strategy = "target_over_complete_short"
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    source_tokens=short_anchor["completion_tokens"],
                    retain_ratio_percent="100.0",
                    remove_ratio_percent="0.0",
                    expand_ratio_percent=f"{expand_ratio * 100:.1f}",
                    general_guidance=responses[source_version].content,
                    direction="expand",
                )
            else:
                operation = "regenerate"
                source_reason = "regenerate_from_problem_no_complete_candidate"
                role = "general_guidance_adjust"
                condition = f"regenerate_{version}"
                rendered = self._rendered_call(
                    role, problem_id, condition, problem,
                    target_tokens=target_tokens,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    direction="regenerate",
                )

            version_dir = stage_root / f"version_{version}"
            compatibility_warnings: list[str] = []
            record_operation = operation
            record_source_version = source_version
            record_source_reason = source_reason
            record_retain_ratio = retain_ratio
            record_remove_ratio = remove_ratio
            record_expand_ratio = expand_ratio
            record_ratio_strategy = ratio_strategy
            record_feedback_source_version = feedback_source_version
            record_revision_feedback = revision_feedback
            record_anchor_long_version = (
                None if long_anchor is None else long_anchor["version"]
            )
            record_anchor_short_version = (
                None if short_anchor is None else short_anchor["version"]
            )
            existing_call = version_dir / "model_call.json"
            if self.config.execution.resume and existing_call.is_file():
                saved = read_json(existing_call)
                expected_prompt_hash = _hash(
                    rendered["system_prompt"] + "\0" + rendered["user_prompt"]
                )
                if saved.get("prompt_hash") != expected_prompt_hash:
                    compatibility_warnings.append(
                        "persisted_legacy_prompt_mismatch_reused"
                    )
                if (saved.get("role") != role or
                        saved.get("condition") != condition):
                    compatibility_warnings.append(
                        "persisted_legacy_operation_mismatch_reused"
                    )
                existing_version = version_dir / "version.json"
                old_record: dict[str, Any] = {}
                if existing_version.is_file():
                    old_record = read_json(existing_version)
                    if "state" not in old_record:
                        compatibility_warnings.append(
                            "persisted_legacy_version_schema_reconstructed"
                        )
                saved_condition = str(saved.get("condition", ""))
                inferred_operation = (
                    "initial" if saved_condition == "initial" else
                    "compress" if saved_condition.startswith("compress_") else
                    "expand" if saved_condition.startswith("expand_") else
                    "regenerate" if saved_condition.startswith("regenerate_") else
                    operation
                )
                record_operation = str(
                    old_record.get("operation", inferred_operation)
                )
                if "source_version" in old_record:
                    record_source_version = old_record["source_version"]
                elif "input_version" in old_record:
                    record_source_version = old_record["input_version"]
                elif record_operation in {"compress", "expand"} and version > 0:
                    record_source_version = version - 1
                    compatibility_warnings.append(
                        "persisted_legacy_source_version_inferred"
                    )
                else:
                    record_source_version = None
                if "source_selection_reason" in old_record:
                    record_source_reason = str(
                        old_record["source_selection_reason"]
                    )
                elif record_operation == "initial":
                    record_source_reason = "initial_generation"
                elif record_operation == "regenerate":
                    record_source_reason = (
                        "persisted_legacy_regeneration_from_problem_inferred"
                    )
                else:
                    record_source_reason = (
                        "persisted_legacy_previous_version_source_inferred"
                    )
                record_retain_ratio = old_record.get(
                    "retain_ratio_requested"
                )
                record_remove_ratio = old_record.get(
                    "remove_ratio_requested"
                )
                record_expand_ratio = old_record.get(
                    "expand_ratio_requested"
                )
                record_ratio_strategy = old_record.get("ratio_strategy")
                record_feedback_source_version = old_record.get(
                    "feedback_source_version"
                )
                record_revision_feedback = old_record.get("revision_feedback")
                record_anchor_long_version = old_record.get(
                    "anchor_long_version"
                )
                record_anchor_short_version = old_record.get(
                    "anchor_short_version"
                )
                if (record_operation in {"compress", "expand"} and
                        record_ratio_strategy is None):
                    compatibility_warnings.append(
                        "persisted_legacy_ratio_metadata_unavailable"
                    )
                if ("anchor_long_version" not in old_record or
                        "anchor_short_version" not in old_record):
                    compatibility_warnings.append(
                        "persisted_legacy_anchor_metadata_unavailable"
                    )
            response, call_path = self._call(
                version_dir, role, problem_id, condition, rendered,
                max_output_tokens=gg_max_output_tokens,
                allow_persisted_max_tokens_mismatch=True,
                allow_persisted_prompt_mismatch=True,
            )
            if response.token_count_source not in {"api_usage", "mock_usage"}:
                raise ModelInfrastructureError(
                    "General Guidance requires API completion_tokens; tokenizer fallback is not accepted"
                )
            responses.append(response)
            content_path = version_dir / "content.md"
            write_text(content_path, response.content)
            validation = validate_guidance_content(response.content)
            status = guidance_candidate_state(
                response, lower_bound, upper_bound,
                validation["semantic_completeness_passed"] and
                not validation["structural_errors"],
            )
            request_max_tokens = read_json(call_path).get("model", {}).get(
                "max_output_tokens", gg_max_output_tokens
            )
            record = guidance_version_record(
                version=version,
                operation=record_operation,
                source_version=record_source_version,
                source_selection_reason=record_source_reason,
                response=response,
                content_path=content_path,
                target_tokens=target_tokens,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                configured_max_tokens=gg_max_output_tokens,
                request_max_tokens=request_max_tokens,
                status=status,
                validation=validation,
                retain_ratio_requested=record_retain_ratio,
                remove_ratio_requested=record_remove_ratio,
                expand_ratio_requested=record_expand_ratio,
                ratio_strategy=record_ratio_strategy,
                feedback_source_version=record_feedback_source_version,
                revision_feedback=record_revision_feedback,
                anchor_long_version=record_anchor_long_version,
                anchor_short_version=record_anchor_short_version,
                compatibility_warnings=compatibility_warnings,
            )
            version_records.append(record)
            write_json(version_dir / "version.json", record)

            if record["matched"]:
                matched_version = version
                stop_reason = "first_valid_candidate_in_interval"
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

        selected_record = (
            version_records[selected_version]
            if selected_version is not None else None
        )
        selected_validation = None if selected_record is None else {
            key: selected_record[key] for key in (
                "preferred_structure", "required_sections_passed",
                "semantic_completeness_passed",
                "covered_categories", "missing_categories", "structural_errors",
                "structural_warnings", "forbidden_content", "obviously_truncated",
            )
        }
        final_anchors = guidance_anchor_records(version_records)
        all_compatibility_warnings = sorted({
            warning
            for item in version_records
            for warning in item["compatibility_warnings"]
        })
        match_record = {
            "target_tokens": target_tokens,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "max_output_tokens": gg_max_output_tokens,
            "output_capacity_policy": {
                "type": "fixed",
                "max_output_tokens": gg_max_output_tokens,
            },
            "max_regeneration_attempts": teaching.max_regeneration_attempts,
            "attempts_used": len(version_records),
            "matched_version": matched_version,
            "selected_version": selected_version,
            "selected_audit_version": selected_version,
            "best_complete_long_version": (
                None if final_anchors["long"] is None
                else final_anchors["long"]["version"]
            ),
            "best_complete_short_version": (
                None if final_anchors["short"] is None
                else final_anchors["short"]["version"]
            ),
            "selection_reason": selection_reason,
            "stop_reason": stop_reason,
            "token_match_passed": passed,
            "token_match_failed": not passed,
            "validation_policy": "semantic_completeness_v1",
            "selected_validation": selected_validation,
            "compatibility_warnings": all_compatibility_warnings,
            "versions": version_records,
        }
        write_json(stage_root / "match.json", match_record)
        if selected_version is None:
            validation_error = (
                "gg_generation_truncated"
                if any(item["is_truncated_candidate"] for item in version_records)
                else "gg_content_validation_failed"
            )
            raise GGContentValidationError(
                "General Guidance produced no semantically complete candidate",
                validation_error=validation_error,
            )
        response = responses[selected_version]
        error = token_relative_error(target_tokens, response.output_tokens)
        return {
            "response": response,
            "metrics": {
                "target_tokens": target_tokens,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "max_output_tokens": gg_max_output_tokens,
                "attempts_used": len(version_records),
                "matched_version": matched_version,
                "selected_version": selected_version,
                "selected_audit_version": selected_version,
                "selection_reason": selection_reason,
                "best_complete_long_version": match_record[
                    "best_complete_long_version"
                ],
                "best_complete_short_version": match_record[
                    "best_complete_short_version"
                ],
                "general_guidance_tokens": response.output_tokens,
                "token_relative_error": error,
                "token_match_passed": passed,
                "token_match_failed": not passed,
                "general_guidance_truncated": response.truncated,
                **(selected_validation or {}),
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
                teacher_planning=values["teacher_planning"],
                teacher_raw_response=values["teacher_raw_response"],
                teacher_code=values["teacher_code"],
            )
        elif role == "failure_frontier":
            system = self.renderer.template("failure_frontier.md")
            user = self.renderer.render(
                self.renderer.template("failure_frontier_user.md"),
                formatted_problem=problem,
                teacher_planning=values["teacher_planning"],
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
                source_tokens=values.get("source_tokens", ""),
                retain_ratio_percent=values.get("retain_ratio_percent", ""),
                remove_ratio_percent=values.get("remove_ratio_percent", ""),
                expand_ratio_percent=values.get("expand_ratio_percent", ""),
                revision_feedback=values.get("revision_feedback", ""),
            )
            if values["direction"] == "regenerate":
                user = problem
            else:
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

    def _rendered_solver_call(
        self, stage: str, role: str, problem_id: str, condition: str,
        problem: str, *, additional_material: str = "",
        success_branch: bool = False, planning_content: str = "",
        planning_status: str = "",
    ) -> dict[str, str]:
        if role == "teacher" or (condition == "success_only" and not success_branch):
            solver_input = problem
        else:
            solver_input = self.renderer.render(
                self.renderer.template("student_user_with_material.md"),
                formatted_problem=problem,
                additional_material=additional_material,
            )
        if stage == "planning":
            system = self.renderer.render(
                self.renderer.template("solver_planning.md"),
                planning_max_output_tokens=self.config.solver.planning_max_output_tokens,
            )
            user = solver_input
        elif stage == "final":
            system = self.renderer.render(
                self.renderer.template("solver_final.md"),
                final_max_output_tokens=self.config.solver.final_max_output_tokens,
            )
            user = self.renderer.render(
                self.renderer.template("solver_final_user.md"),
                solver_input=solver_input,
                planning_status=planning_status,
                planning_content=planning_content,
            )
        else:
            raise ValueError(f"unsupported solver stage: {stage}")
        return {
            "role": f"{role}_{stage}", "problem_id": problem_id,
            "condition": condition, "system_prompt": system, "user_prompt": user,
        }

    def _call(self, stage_dir: Path, role: str, problem_id: str, condition: str,
              rendered: dict[str, str], *,
              max_output_tokens: int | None = None,
              allow_persisted_max_tokens_mismatch: bool = False,
              allow_persisted_prompt_mismatch: bool = False,
              ) -> tuple[ModelResponse, Path]:
        artifact = stage_dir / "model_call.json"
        effective_max_tokens = (
            self.config.model.max_output_tokens
            if max_output_tokens is None else max_output_tokens
        )
        if self.config.execution.resume and artifact.is_file():
            saved = read_json(artifact)
            if saved.get("status") == "completed":
                if (not allow_persisted_max_tokens_mismatch and
                        saved.get("model", {}).get("max_output_tokens") !=
                        effective_max_tokens):
                    raise ModelInfrastructureError(
                        "persisted model call max_output_tokens differs from current request"
                    )
                expected_prompt_hash = _hash(
                    rendered["system_prompt"] + "\0" + rendered["user_prompt"]
                )
                if (not allow_persisted_prompt_mismatch and
                        saved.get("prompt_hash") != expected_prompt_hash):
                    raise ModelInfrastructureError(
                        "persisted model call prompt hash differs from current request"
                    )
                saved_model = saved.get("model", {})
                if (saved_model.get("model_name") != self.config.model.model_name or
                        saved_model.get("reasoning_mode") !=
                        self.config.model.reasoning_mode or
                        saved_model.get("temperature") != self.config.model.temperature or
                        saved_model.get("top_p") != self.config.model.top_p):
                    raise ModelInfrastructureError(
                        "persisted model call configuration differs from current request"
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


def condition_comparison_eligible(record: dict[str, Any]) -> bool:
    """Derive the final comparison gate from episode validity invariants."""
    return (
        record.get("valid_episode") is True and
        not record.get("infrastructure_error") and
        not record.get("protocol_output_invalid") and
        not record.get("token_match_failed")
    )


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


def _normalized_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _guidance_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    return [
        (
            _normalized_heading(match.group(1)),
            text[match.end():matches[index + 1].start()
                 if index + 1 < len(matches) else len(text)].strip(),
        )
        for index, match in enumerate(matches)
    ]


def _signal_count(category: str, text: str) -> int:
    return sum(
        bool(re.search(pattern, text, flags=re.IGNORECASE))
        for pattern in GG_CATEGORY_SIGNALS[category]
    )


def _substantive(text: str, minimum_words: int = 5) -> bool:
    return len(re.findall(r"\b[\w-]+\b", text)) >= minimum_words


def _obviously_incomplete(text: str, sections: list[tuple[str, str]]) -> bool:
    if not text:
        return True
    if text.count("```") % 2:
        return True
    if sections and not sections[-1][1].strip():
        return True
    last_line = text.splitlines()[-1].strip()
    if (last_line.startswith("#") or last_line in {"-", "*", "+"} or
            re.match(r"^(?:[-*+]\s*|\d+[.)]\s*)$", last_line) or
            last_line.endswith((":", ",", ";", "-", "(", "[", "{"))):
        return True
    if re.search(
        r"\b(?:and|or|because|therefore|which|that|with|without|to|such as)\s*$",
        last_line, flags=re.IGNORECASE,
    ):
        return True
    return False


def validate_guidance_content(content: str) -> dict[str, Any]:
    """Return auditable GG format signals and semantic protocol validity."""
    text = content.strip()
    errors: list[str] = []
    warnings: list[str] = []
    forbidden: list[str] = []
    if not text:
        return {
            "preferred_structure": False,
            "required_sections_passed": False,
            "semantic_completeness_passed": False,
            "covered_categories": [],
            "missing_categories": list(GG_CATEGORIES),
            "structural_errors": ["empty_content"],
            "structural_warnings": [],
            "forbidden_content": [],
            "obviously_truncated": False,
        }

    sections = _guidance_sections(text)
    exact_headings = tuple(_normalized_heading(item) for item in GG_REQUIRED_SECTIONS)
    actual_headings = tuple(heading for heading, _ in sections)
    exact_positions = [
        actual_headings.index(heading) if heading in actual_headings else -1
        for heading in exact_headings
    ]
    preferred_structure = (
        all(position >= 0 for position in exact_positions) and
        exact_positions == sorted(exact_positions) and
        all(sections[position][1].strip() for position in exact_positions)
    )
    if not preferred_structure:
        errors.append("required_sections_missing_or_invalid")

    covered: set[str] = set()
    for heading, body in sections:
        for category, aliases in GG_SECTION_ALIASES.items():
            if (heading in aliases and _substantive(body) and
                    _signal_count(category, body) >= 1):
                covered.add(category)

    # Heading-free and unconventional prose is accepted only when a localized
    # paragraph has multiple independent signals for a category.  This avoids
    # treating one accidental keyword in the whole response as coverage.
    paragraphs = [
        re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", block).strip()
        for block in re.split(r"\n\s*\n", text)
        if block.strip() and not block.lstrip().startswith("#")
    ]
    for category in GG_CATEGORIES:
        if category in covered:
            continue
        if any(
            _substantive(paragraph, minimum_words=8) and
            _signal_count(category, paragraph) >= 2
            for paragraph in paragraphs
        ):
            covered.add(category)

    if re.search(r"```", text):
        forbidden.append("code_fence")
        errors.append("code_fence_not_allowed")
    if re.search(
        r"(?ms)^\s*(?:class\s+\w+[^\n]*:|def\s+\w+\s*\([^\n]*\)\s*:)[^\n]*\n"
        r"(?:[ \t]+\S.*\n?){2,}",
        text,
    ):
        forbidden.append("complete_solution_code")
        errors.append("complete_solution_code_not_allowed")
    leakage_patterns = {
        "hidden_test_claim": r"\b(?:I|we)\s+(?:know|saw|inspected).{0,30}\bhidden tests?\b",
        "oracle_or_judge_claim": r"\b(?:oracle|judge internals?)\s+(?:shows?|reveals?|contains?)\b",
        "prior_attempt_reference": r"\b(?:teacher response|failure frontier|judge verdict)\b",
        "sentinel_leak": r"\b(?:TEACHER|VERDICT|FF|HIDDEN_TEST|JUDGE)_[A-Z_]*SENTINEL\b",
    }
    for label, pattern in leakage_patterns.items():
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            forbidden.append(label)
            errors.append(f"forbidden_{label}")

    truncated = _obviously_incomplete(text, sections)
    if truncated:
        errors.append("obviously_incomplete_ending")
    missing = [category for category in GG_CATEGORIES if category not in covered]
    if missing:
        errors.append("semantic_categories_missing")
    return {
        "preferred_structure": preferred_structure,
        "required_sections_passed": preferred_structure,
        "semantic_completeness_passed": (
            preferred_structure and not missing and not forbidden and not truncated
        ),
        "covered_categories": [item for item in GG_CATEGORIES if item in covered],
        "missing_categories": missing,
        "structural_errors": errors,
        "structural_warnings": warnings,
        "forbidden_content": forbidden,
        "obviously_truncated": truncated,
    }


def guidance_candidate_state(
    response: ModelResponse,
    lower_bound: int,
    upper_bound: int,
    valid_content: bool,
) -> str:
    if response.finish_reason == "length":
        return "TRUNCATED_TOO_LONG"
    if not valid_content:
        return "INVALID_CONTENT"
    if response.finish_reason != "stop":
        return "INVALID_CONTENT"
    if response.output_tokens is None:
        raise ModelInfrastructureError(
            "reliable General Guidance completion token usage is required"
        )
    if response.output_tokens < lower_bound:
        return "TOO_SHORT"
    if response.output_tokens > upper_bound:
        return "COMPLETE_TOO_LONG"
    return "MATCHED"


def guidance_anchor_records(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    def closest(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        return min(
            candidates,
            key=lambda item: (item["distance_to_target"], item["version"]),
            default=None,
        )

    return {
        "long": closest([
            item for item in records if item["is_complete_long_candidate"]
        ]),
        "short": closest([
            item for item in records if item["is_complete_short_candidate"]
        ]),
        "matched": closest([
            item for item in records if item["matched"]
        ]),
    }


def guidance_retain_ratio(
    target_tokens: int,
    long_record: dict[str, Any],
    short_record: dict[str, Any] | None,
    *,
    previous_compression: dict[str, Any] | None = None,
) -> tuple[float, str]:
    long_tokens = long_record["completion_tokens"]
    base_ratio = target_tokens / long_tokens
    strategy = "target_over_complete_long"
    ratio = base_ratio
    observation = previous_compression or short_record
    if (observation is not None and
            observation.get("source_version") == long_record["version"] and
            observation.get("retain_ratio_requested") is not None and
            observation.get("finish_reason") == "stop"):
        observed_tokens = observation["completion_tokens"]
        previous = float(observation["retain_ratio_requested"])
        if observed_tokens < target_tokens < long_tokens:
            interpolation = (target_tokens - observed_tokens) / (
                long_tokens - observed_tokens
            )
            ratio = previous + (1.0 - previous) * interpolation
            strategy = (
                "linear_correction_from_complete_long_and_short"
                if observation.get("is_complete_short_candidate")
                else "linear_correction_from_previous_invalid_compression"
            )
        elif observed_tokens > target_tokens:
            ratio = previous * target_tokens / observed_tokens
            strategy = "proportional_correction_from_previous_compression"
        else:
            ratio = previous
            strategy = "retain_previous_ratio_for_content_repair"
    return min(0.98, max(0.50, ratio)), strategy


def guidance_latest_compression(
    records: list[dict[str, Any]], long_version: int,
) -> dict[str, Any] | None:
    candidates = [
        item for item in records
        if item.get("operation") == "compress" and
        item.get("source_version") == long_version and
        item.get("finish_reason") == "stop" and
        item.get("retain_ratio_requested") is not None
    ]
    return max(candidates, key=lambda item: item["version"], default=None)


def guidance_compression_feedback(
    previous: dict[str, Any], lower_bound: int, upper_bound: int,
) -> str:
    missing = previous.get("missing_categories", [])
    labels = {
        "constraints": "constraint analysis",
        "approaches": "algorithmic directions",
        "correctness": "correctness and edge-case coverage",
        "implementation": "substantive implementation coverage",
    }
    if missing:
        reason = " and ".join(labels[item] for item in missing)
        opening = (
            "The previous compressed version was invalid because it omitted "
            f"{reason}."
        )
    elif previous.get("structural_errors"):
        opening = (
            "The previous compressed version was invalid because it did not "
            "satisfy the required four-section content protocol."
        )
    else:
        opening = "The previous compressed version did not satisfy the target interval."
    allocation = ""
    if missing:
        allocation_labels = {
            "constraints": "constraint analysis",
            "approaches": "algorithmic directions",
            "correctness": "correctness and edge cases",
            "implementation": "implementation checks",
        }
        named = " and ".join(allocation_labels[item] for item in missing)
        allocation = (
            "\n\nIn this revision, preserve all four required sections and allocate "
            f"approximately 20% of the response to {named}."
        )
    length_warning = ""
    tokens = previous["completion_tokens"]
    if tokens < lower_bound:
        length_warning = "\n\nDo not repeat the previous over-compression."
    elif tokens > upper_bound:
        length_warning = "\n\nReduce more decisively while preserving every section."
    return opening + allocation + length_warning


def guidance_version_record(
    *,
    version: int,
    operation: str,
    source_version: int | None,
    source_selection_reason: str,
    response: ModelResponse,
    content_path: Path,
    target_tokens: int,
    lower_bound: int,
    upper_bound: int,
    configured_max_tokens: int,
    request_max_tokens: int,
    status: str,
    validation: dict[str, Any],
    retain_ratio_requested: float | None,
    remove_ratio_requested: float | None,
    expand_ratio_requested: float | None,
    ratio_strategy: str | None,
    feedback_source_version: int | None,
    revision_feedback: str | None,
    anchor_long_version: int | None,
    anchor_short_version: int | None,
    compatibility_warnings: list[str],
) -> dict[str, Any]:
    if response.output_tokens is None:
        raise ModelInfrastructureError(
            "reliable General Guidance completion token usage is required"
        )
    tokens = response.output_tokens
    valid_content = (
        validation["semantic_completeness_passed"] and
        not validation["structural_errors"]
    )
    valid_candidate = response.finish_reason == "stop" and valid_content
    return {
        "version": version,
        "operation": operation,
        "input_version": source_version,
        "source_version": source_version,
        "source_selection_reason": source_selection_reason,
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
        "state": status,
        "accepted_lower_bound": lower_bound,
        "accepted_upper_bound": upper_bound,
        "is_complete_long_candidate": status == "COMPLETE_TOO_LONG",
        "is_complete_short_candidate": status == "TOO_SHORT",
        "is_truncated_candidate": status == "TRUNCATED_TOO_LONG",
        "retain_ratio_requested": retain_ratio_requested,
        "remove_ratio_requested": remove_ratio_requested,
        "expand_ratio_requested": expand_ratio_requested,
        "ratio_strategy": ratio_strategy,
        "feedback_source_version": feedback_source_version,
        "revision_feedback": revision_feedback,
        "anchor_long_version": anchor_long_version,
        "anchor_short_version": anchor_short_version,
        "validation_error": (
            "gg_generation_truncated"
            if status == "TRUNCATED_TOO_LONG" else None
        ),
        "compatibility_warnings": compatibility_warnings,
        "preferred_structure": validation["preferred_structure"],
        "required_sections_passed": validation["required_sections_passed"],
        "semantic_completeness_passed": validation[
            "semantic_completeness_passed"
        ],
        "covered_categories": validation["covered_categories"],
        "missing_categories": validation["missing_categories"],
        "structural_errors": validation["structural_errors"],
        "structural_warnings": validation["structural_warnings"],
        "forbidden_content": validation["forbidden_content"],
        "obviously_truncated": validation["obviously_truncated"],
        "configured_max_tokens": configured_max_tokens,
        "request_max_tokens": request_max_tokens,
    }


def _solver_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result[key] for key in (
        "verdict", "input_tokens", "output_tokens", "truncated", "format_error",
        "solver_protocol", "planning_calls", "final_calls", "judge_submissions",
        "planning_truncated", "final_truncated", "final_code_extracted",
        "final_verdict", "planning_validation_warnings", "output_failure_category",
    )}


def _planning_warnings(response: ModelResponse) -> list[str]:
    warnings: list[str] = []
    text = response.content.strip()
    if not text:
        warnings.append("planning_output_empty")
    required = (
        "## Candidate Analysis", "## Selected Algorithm",
        "## State or Invariant", "## Complexity",
    )
    if text and any(section not in text for section in required):
        warnings.append("planning_structure_incomplete")
    if "```" in text:
        warnings.append("planning_code_fence_present")
    if response.truncated:
        warnings.append("planning_truncated")
    return warnings


def _stage_metadata(
    stage: str, max_tokens: int, response: ModelResponse,
    call_path: Path, warnings: list[str],
) -> dict[str, Any]:
    call = read_json(call_path)
    return {
        "stage": stage,
        "max_output_tokens": max_tokens,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "finish_reason": response.finish_reason,
        "truncated": response.truncated,
        "content_empty": not response.content.strip(),
        "validation_warnings": warnings,
        "response_id": response.response_id,
        "prompt_hash": call.get("prompt_hash"),
    }


def build_summary(run_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [record for record in records if record.get("valid_episode")]
    comparable = [
        record for record in valid
        if record.get("condition_comparison_eligible", False)
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
