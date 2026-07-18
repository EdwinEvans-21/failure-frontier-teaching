from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import csv
import hashlib
import itertools
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time

from experiments.pilot.code_extraction import extract_fenced_python_submission
from experiments.pilot.config import ModelConfig
from experiments.pilot.model_client import (
    DeepSeekCompatibleClient,
    MockModelClient,
    ModelClient,
    ModelInfrastructureError,
    ModelResponse,
)
from experiments.pilot.prompts import PromptRenderer
from experiments.pilot.storage import read_json, write_json, write_text
from ffjudge.models import JudgeResult, ProblemSpec, Verdict
from ffjudge.runner import DockerJudge, DockerUnavailableError

from .schedule import CONDITIONS, PROBLEM_IDS, build_schedule, validate_schedule
from .source import ELIGIBILITY_POLICY, sha256_file, sha256_text, verify_fixed_material_snapshot


VERDICTS = {
    Verdict.ACCEPTED: "AC",
    Verdict.WRONG_ANSWER: "WA",
    Verdict.SYNTAX_ERROR: "CE",
    Verdict.INVALID_SUBMISSION: "CE",
    Verdict.RUNTIME_ERROR: "RE",
    Verdict.TIME_LIMIT_EXCEEDED: "TLE",
    Verdict.MEMORY_LIMIT_EXCEEDED: "MLE",
    Verdict.INTERNAL_ERROR: "JUDGE_ERROR",
}


def fixed_material_cell_eligibility(
    *, source_episode_strictly_eligible: bool,
    fixed_material_hashes_verified: bool,
    correct_condition_material_used: bool,
    planning_call_completed: bool,
    final_call_completed: bool,
    infrastructure_error: bool,
) -> tuple[bool, list[str]]:
    checks = {
        "source_episode_not_strictly_eligible": source_episode_strictly_eligible,
        "fixed_material_hashes_not_verified": fixed_material_hashes_verified,
        "incorrect_condition_material": correct_condition_material_used,
        "planning_call_incomplete": planning_call_completed,
        "final_call_incomplete": final_call_completed,
        "infrastructure_error": not infrastructure_error,
    }
    reasons = [reason for reason, passed in checks.items() if not passed]
    return not reasons, reasons


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_request(system: str, user: str, parameters: dict[str, Any]) -> str:
    payload = json.dumps(
        {"system": system, "user": user, "parameters": parameters},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return sha256_text(payload)


class FixedMaterialRunner:
    def __init__(
        self,
        config_path: Path,
        snapshot_root: Path,
        output_root: Path,
        *,
        mode: str,
        project_root: Path,
        model: ModelClient | None = None,
        judge: Any | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.config_path = config_path.resolve()
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.snapshot_root = snapshot_root.resolve()
        self.output_root = output_root.resolve()
        self.mode = mode
        if mode not in {"dry-run", "mock", "live"}:
            raise ValueError("unsupported fixed-material mode")
        self.model_config = ModelConfig(**self.config["model"])
        self.model = model
        if self.model is None and mode == "live":
            self.model = DeepSeekCompatibleClient(self.model_config)
        if self.model is None and mode == "mock":
            self.model = MockModelClient(self.model_config)
        self.judge = judge or DockerJudge(self.config["execution"]["judge_image"])
        self.renderer = PromptRenderer(self.project_root / self.config["prompts_dir"])
        self.manifest = read_json(self.snapshot_root / "fixed_material_manifest.json")
        self.run_dir: Path | None = None

    def verify_preconditions(self) -> dict[str, Any]:
        review = verify_fixed_material_snapshot(self.snapshot_root, self.project_root)
        if not review["passed"]:
            raise RuntimeError("fixed material verification failed")
        checks: dict[str, Any] = {"fixed_material": review}
        for label, tool in (
            ("baseline_v3", "verify_baseline_v3_manifest.py"),
            ("expanded_baseline", "verify_baseline_v3_expanded_manifest.py"),
        ):
            completed = subprocess.run(
                [sys.executable, str(self.project_root / "tools" / tool)],
                cwd=self.project_root, capture_output=True, text=True, check=False,
            )
            checks[label] = {
                "passed": completed.returncode == 0,
                "exit_code": completed.returncode,
                "output": (completed.stdout + completed.stderr).strip(),
            }
            if completed.returncode:
                raise RuntimeError(f"{label} verification failed")
        return checks

    def dry_run(self, run_id: str) -> dict[str, Any]:
        checks = self.verify_preconditions()
        schedule = build_schedule(run_id)
        result = {
            "run_id": run_id,
            "mode": "dry-run",
            "problem_count": 7,
            "condition_count": 4,
            "replicates": 10,
            "student_episodes": 280,
            "maximum_api_calls": 560,
            "maximum_judge_submissions": 280,
            "api_accessed": False,
            "judge_accessed": False,
            "schedule_valid": True,
            "preconditions": checks,
        }
        return result

    def preflight(self, run_id: str, *, resume: bool = False) -> dict[str, Any]:
        checks = self.verify_preconditions()
        schedule = build_schedule(run_id)
        run_dir = self.output_root / run_id
        if run_dir.exists() and not resume:
            raise FileExistsError("run directory already exists")
        run_dir.mkdir(parents=True, exist_ok=resume)
        self.run_dir = run_dir
        prompt_paths = [
            "solver_planning.md", "solver_final.md", "solver_final_user.md",
            "student_user_with_material.md", "student_user_with_critical_ff.md",
        ]
        prompt_hashes = {
            name: sha256_file(self.project_root / self.config["prompts_dir"] / name)
            for name in prompt_paths
        }
        git = self._git_identity()
        if self.mode == "live" and not git["working_tree_clean"]:
            raise RuntimeError("working tree must be clean before live execution")
        preflight = {
            "schema_version": "1.0",
            "run_type": "fixed_material_repeated_student_v1",
            "run_id": run_id,
            "created_at": now(),
            "git_commit": git["commit"],
            "runner_tags": git["tags"],
            "working_tree_clean": git["working_tree_clean"],
            "fixed_material_manifest": str(
                self.snapshot_root / "fixed_material_manifest.json"
            ),
            "fixed_material_manifest_sha256": sha256_file(
                self.snapshot_root / "fixed_material_manifest.json"
            ),
            "source_run_id": self.manifest["source_run_id"],
            "source_runner_commit": self.manifest["source_runner_commit"],
            "source_runner_tag": self.manifest["source_runner_tag"],
            "source_baseline_id": self.manifest["source_baseline_id"],
            "source_baseline_manifest_sha256": self.manifest[
                "source_baseline_manifest_sha256"
            ],
            "config_sha256": sha256_file(self.config_path),
            "prompt_hashes": prompt_hashes,
            "model": {
                "provider": self.model_config.provider,
                "model_name": self.model_config.model_name,
                "thinking": self.model_config.thinking,
                "temperature": self.model_config.temperature,
                "top_p": self.model_config.top_p,
                "stream": False,
                "seed": self.model_config.seed,
            },
            "planning_max_output_tokens": self.config["solver"][
                "planning_max_output_tokens"
            ],
            "final_max_output_tokens": self.config["solver"][
                "final_max_output_tokens"
            ],
            "problem_ids": list(PROBLEM_IDS),
            "conditions": list(CONDITIONS),
            "planned_cells": 280,
            "maximum_api_calls": 560,
            "maximum_judge_submissions": 280,
            "execution_schedule_sha256": sha256_text(json.dumps(
                schedule, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )),
            "output_directory": str(run_dir),
            "precondition_checks": checks,
        }
        write_json(run_dir / "preflight_manifest.json", preflight)
        write_json(run_dir / "execution_schedule.json", schedule)
        write_json(run_dir / "fixed_material_manifest.json", self.manifest)
        write_json(run_dir / "preflight_review.json", {
            "passed": True,
            "reviewed_at": now(),
            "schedule_cells": len(schedule),
            "material_hashes_verified": True,
            "prompt_hashes_recorded": True,
            "api_accessed": False,
            "judge_accessed": False,
        })
        shutil.copyfile(self.config_path, run_dir / "config.snapshot.json")
        return preflight

    def run(self, run_id: str, *, resume: bool = False) -> dict[str, Any]:
        if self.mode == "dry-run":
            return self.dry_run(run_id)
        if resume:
            self.run_dir = self.output_root / run_id
            if not self.run_dir.is_dir():
                raise FileNotFoundError("resume run directory does not exist")
            preflight = read_json(self.run_dir / "preflight_manifest.json")
            self._verify_locked_preflight(preflight)
        else:
            preflight = self.preflight(run_id)
        assert self.run_dir is not None
        schedule = read_json(self.run_dir / "execution_schedule.json")
        validate_schedule(schedule)
        write_json(self.run_dir / "run_manifest.json", {
            "run_id": run_id, "status": "running", "started_at": now(),
            "resume": resume, "pid": os.getpid(), "policy": ELIGIBILITY_POLICY,
        })
        started = time.monotonic()
        records: list[dict[str, Any]] = []
        for row in schedule:
            record = self._run_cell(row)
            records.append(record)
            self._write_partial(records)
        result = self._finalize(records, time.monotonic() - started)
        write_json(self.run_dir / "run_manifest.json", {
            "run_id": run_id, "status": "completed", "started_at": preflight["created_at"],
            "completed_at": now(), "policy": ELIGIBILITY_POLICY,
            "planned_cells": 280, "completed_cells": len(records),
        })
        return result

    def _run_cell(self, row: dict[str, Any]) -> dict[str, Any]:
        assert self.run_dir is not None
        cell_dir = self.run_dir / "cells" / row["cell_id"]
        record_path = cell_dir / "sample_record.json"
        if record_path.is_file():
            saved = read_json(record_path)
            if saved.get("pipeline_outcome") == "completed":
                return saved
        snapshot_review = verify_fixed_material_snapshot(
            self.snapshot_root, self.project_root
        )
        if not snapshot_review["passed"]:
            raise RuntimeError("fixed material changed during execution")
        problem_id = row["problem_id"]
        condition = row["condition"]
        material_record = self.manifest["materials"][problem_id]
        material_root = self.snapshot_root / "materials" / problem_id
        formatted_problem = (material_root / "formatted_problem.md").read_text(
            encoding="utf-8"
        )
        ff = (material_root / "failure_frontier.md").read_text(encoding="utf-8")
        gg = (material_root / "general_guidance.md").read_text(encoding="utf-8")
        material = ""
        if condition in {"naive_ff", "critical_ff"}:
            material = ff
        elif condition == "general_guidance":
            material = gg
        solver_input = self._solver_input(condition, formatted_problem, material)
        planning_system = self.renderer.render(
            self.renderer.template("solver_planning.md"),
            planning_max_output_tokens=self.config["solver"][
                "planning_max_output_tokens"
            ],
        )
        hashes = {
            "system_prompt_hash": sha256_text(planning_system),
            "planning_user_prompt_hash": sha256_text(solver_input),
            "material_hash": sha256_text(material) if material else None,
        }
        if condition in {"naive_ff", "critical_ff"} and hashes["material_hash"] != \
                material_record["failure_frontier_sha256"]:
            raise RuntimeError("FF material hash mismatch")
        started = time.monotonic()
        try:
            planning = self._model_stage(
                cell_dir / "planning", "student_planning", problem_id, condition,
                planning_system, solver_input,
                self.config["solver"]["planning_max_output_tokens"],
            )
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
            final_system = self.renderer.render(
                self.renderer.template("solver_final.md"),
                final_max_output_tokens=self.config["solver"]["final_max_output_tokens"],
            )
            final_user = self.renderer.render(
                self.renderer.template("solver_final_user.md"),
                solver_input=solver_input,
                planning_status=planning_status,
                planning_content=planning_content,
            )
            hashes["final_system_prompt_hash"] = sha256_text(final_system)
            hashes["final_user_prompt_hash"] = sha256_text(final_user)
            final = self._model_stage(
                cell_dir / "final", "student_final", problem_id, condition,
                final_system, final_user,
                self.config["solver"]["final_max_output_tokens"],
            )
        except ModelInfrastructureError as error:
            write_json(record_path, {
                **row, **hashes, "pipeline_outcome": "infrastructure_error",
                "valid_sample_cell": False, "comparison_eligible": False,
                "comparison_ineligibility_reasons": ["model_infrastructure_error"],
                "infrastructure_error": type(error).__name__, "success": 0,
            })
            raise
        extraction = extract_fenced_python_submission(final.content)
        write_json(cell_dir / "extraction.json", asdict(extraction))
        judge_attempted = False
        judge_verdict = "CE"
        judge_runtime_ms: int | None = None
        if extraction.ok:
            submission = cell_dir / "submission.py"
            write_text(submission, extraction.code or "")
            problem_path = self.project_root / material_record["repository_problem_path"]
            hidden_path = self.project_root / material_record["repository_hidden_tests_path"]
            try:
                judge_attempted = True
                result: JudgeResult = self.judge.judge(
                    submission, problem_path, hidden_path, phase="hidden"
                )
            except (DockerUnavailableError, OSError, ValueError) as error:
                write_json(cell_dir / "judge_result.json", {
                    "infrastructure_error": True, "error_category": type(error).__name__
                })
                write_json(record_path, {
                    **row, **hashes, "pipeline_outcome": "infrastructure_error",
                    "valid_sample_cell": False, "comparison_eligible": False,
                    "comparison_ineligibility_reasons": ["judge_infrastructure_error"],
                    "infrastructure_error": type(error).__name__, "success": 0,
                })
                raise RuntimeError("judge infrastructure error") from error
            judge_verdict = VERDICTS[result.verdict]
            judge_runtime_ms = result.runtime_ms
            if judge_verdict == "JUDGE_ERROR":
                raise RuntimeError("judge returned infrastructure error")
            write_json(cell_dir / "judge_result.json", {
                "submitted": True, "verdict": judge_verdict,
                "runtime_ms": judge_runtime_ms,
            })
        else:
            write_json(cell_dir / "judge_result.json", {
                "submitted": False, "verdict": "CE",
                "failure_type": "OUTPUT_FORMAT_ERROR",
                "extraction_error": extraction.error,
            })
        hashes["complete_request_hash"] = sha256_text(
            hashes["system_prompt_hash"] + hashes["planning_user_prompt_hash"] +
            hashes["final_system_prompt_hash"] + hashes["final_user_prompt_hash"]
        )
        record = {
            **row, **hashes,
            "eligibility_policy": ELIGIBILITY_POLICY,
            "source_episode_strictly_eligible": True,
            "fixed_material_hashes_verified": True,
            "correct_condition_material_used": True,
            "planning_call_completed": True,
            "final_call_completed": True,
            "infrastructure_error": None,
            "valid_sample_cell": True,
            "comparison_eligible": True,
            "comparison_ineligibility_reasons": [],
            "pipeline_outcome": "completed",
            "planning_truncated": planning.truncated,
            "final_truncated": final.truncated,
            "code_extraction_succeeded": extraction.ok,
            "extraction_error": extraction.error,
            "judge_submission_attempted": judge_attempted,
            "judge_verdict": judge_verdict,
            "success": int(judge_verdict == "AC"),
            "planning_prompt_tokens": planning.input_tokens,
            "planning_completion_tokens": planning.output_tokens,
            "final_prompt_tokens": final.input_tokens,
            "final_completion_tokens": final.output_tokens,
            "total_tokens": (planning.total_tokens or 0) + (final.total_tokens or 0),
            "model_calls": 2,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "completed_at": now(),
        }
        write_json(record_path, record)
        return record

    def _solver_input(self, condition: str, problem: str, material: str) -> str:
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

    def _model_stage(
        self, stage_dir: Path, role: str, problem_id: str, condition: str,
        system: str, user: str, max_tokens: int,
    ) -> ModelResponse:
        response_path = stage_dir / "response.json"
        request_path = stage_dir / "request.json"
        parameters = {
            "provider": self.model_config.provider,
            "base_url": self.model_config.base_url,
            "model": self.model_config.model_name,
            "thinking": self.model_config.thinking,
            "temperature": self.model_config.temperature,
            "top_p": self.model_config.top_p,
            "max_tokens": max_tokens,
            "stream": False,
            "seed": self.model_config.seed,
        }
        request_hash = hash_request(system, user, parameters)
        if response_path.is_file():
            saved = read_json(response_path)
            if saved.get("request_hash") != request_hash:
                raise ModelInfrastructureError("persisted response prompt/config mismatch")
            return ModelResponse(**saved["response"])
        state_path = stage_dir / "call.state.json"
        if state_path.is_file():
            state = read_json(state_path)
            if state.get("status") == "requesting":
                raise ModelInfrastructureError(
                    "ambiguous persisted API call; manual audit required"
                )
        write_json(request_path, {
            "role": role, "problem_id": problem_id, "condition": condition,
            "system_prompt": system, "user_prompt": user,
            "parameters": parameters, "request_hash": request_hash,
            "api_key_persisted": False,
        })
        write_json(state_path, {
            "status": "requesting", "request_hash": request_hash,
            "started_at": now(),
        })
        assert self.model is not None
        try:
            response = self.model.complete(
                role=role, problem_id=problem_id, condition=condition,
                system_prompt=system, user_prompt=user, max_output_tokens=max_tokens,
            )
        except ModelInfrastructureError:
            write_json(state_path, {
                "status": "failed_before_valid_response",
                "request_hash": request_hash, "failed_at": now(),
            })
            raise
        if (
            response.reasoning_content not in (None, "")
            or type(response.input_tokens) is not int or response.input_tokens < 0
            or type(response.output_tokens) is not int or response.output_tokens <= 0
            or type(response.total_tokens) is not int or response.total_tokens <= 0
            or response.token_count_source != "api_usage" and self.mode == "live"
        ):
            raise ModelInfrastructureError("response failed API usage/non-reasoning validation")
        write_json(response_path, {
            "status": "completed", "request_hash": request_hash,
            "response": asdict(response), "completed_at": now(),
        })
        write_json(state_path, {
            "status": "completed", "request_hash": request_hash,
            "response_path": str(response_path), "completed_at": now(),
        })
        write_text(stage_dir / "content.md", response.content)
        return response

    def _write_partial(self, records: list[dict[str, Any]]) -> None:
        assert self.run_dir is not None
        write_text(self.run_dir / "results.jsonl", "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in records
        ))

    def _finalize(self, records: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
        assert self.run_dir is not None
        valid = [row for row in records if row["valid_sample_cell"]]
        condition_summary: dict[str, Any] = {}
        problem_summary: dict[str, Any] = {}
        for condition in CONDITIONS:
            rows = [row for row in valid if row["condition"] == condition]
            successes = sum(row["success"] for row in rows)
            condition_summary[condition] = self._condition_metrics(rows, successes)
        for problem_id in PROBLEM_IDS:
            problem_summary[problem_id] = {}
            for condition in CONDITIONS:
                rows = [row for row in valid if row["problem_id"] == problem_id
                        and row["condition"] == condition]
                successes = sum(row["success"] for row in rows)
                problem_summary[problem_id][condition] = {
                    "successes": successes, "denominator": len(rows),
                    "ac_rate": successes / len(rows) if rows else None,
                }
        differences = self._differences(problem_summary)
        summary = {
            "planned_cells": 280,
            "completed_cells": len(records),
            "valid_cells": len(valid),
            "invalid_cells": len(records) - len(valid),
            "model_calls": sum(row.get("model_calls", 0) for row in records),
            "judge_submissions": sum(bool(row.get("judge_submission_attempted")) for row in records),
            "prompt_tokens": sum(
                (row.get("planning_prompt_tokens") or 0) +
                (row.get("final_prompt_tokens") or 0) for row in records
            ),
            "completion_tokens": sum(
                (row.get("planning_completion_tokens") or 0) +
                (row.get("final_completion_tokens") or 0) for row in records
            ),
            "total_tokens": sum(row.get("total_tokens", 0) for row in records),
            "elapsed_seconds": round(elapsed, 3),
            "condition_summary": condition_summary,
            "problem_condition_summary": problem_summary,
            "estimands": differences,
            "resampling_count": 0,
        }
        self._write_csv(records)
        write_json(self.run_dir / "summary.json", summary)
        write_json(self.run_dir / "condition_summary.json", condition_summary)
        write_json(self.run_dir / "problem_condition_summary.json", problem_summary)
        write_json(self.run_dir / "api_usage_summary.json", {
            key: summary[key] for key in (
                "model_calls", "prompt_tokens", "completion_tokens", "total_tokens"
            )
        })
        write_json(self.run_dir / "judge_summary.json", {
            "submission_count": summary["judge_submissions"],
            "verdicts": dict(Counter(row.get("judge_verdict") for row in valid)),
        })
        write_json(self.run_dir / "format_failure_summary.json", {
            condition: sum(
                row["condition"] == condition and not row["code_extraction_succeeded"]
                for row in valid
            ) for condition in CONDITIONS
        })
        write_json(self.run_dir / "truncation_summary.json", {
            condition: {
                "planning": sum(row["condition"] == condition and row["planning_truncated"]
                                for row in valid),
                "final": sum(row["condition"] == condition and row["final_truncated"]
                             for row in valid),
            } for condition in CONDITIONS
        })
        write_text(self.run_dir / "summary.md", self._summary_markdown(summary))
        self._build_blinded_package(valid)
        integrity = self._integrity(records)
        write_json(self.run_dir / "integrity_report.json", integrity)
        self._artifact_hashes()
        return summary

    @staticmethod
    def _condition_metrics(rows: list[dict[str, Any]], successes: int) -> dict[str, Any]:
        n = len(rows)
        rate = successes / n if n else None
        interval = _wilson(successes, n) if n else [None, None]
        return {
            "successes": successes, "denominator": n, "micro_ac_rate": rate,
            "wilson_95": interval,
            "planning_truncation_rate": sum(r["planning_truncated"] for r in rows) / n if n else None,
            "final_truncation_rate": sum(r["final_truncated"] for r in rows) / n if n else None,
            "extraction_failure_rate": sum(not r["code_extraction_succeeded"] for r in rows) / n if n else None,
            "judge_submission_rate": sum(r["judge_submission_attempted"] for r in rows) / n if n else None,
            "verdicts": dict(Counter(r["judge_verdict"] for r in rows)),
            "average_prompt_tokens": sum((r["planning_prompt_tokens"] or 0) +
                                         (r["final_prompt_tokens"] or 0) for r in rows) / n if n else None,
            "average_completion_tokens": sum((r["planning_completion_tokens"] or 0) +
                                             (r["final_completion_tokens"] or 0) for r in rows) / n if n else None,
            "average_wall_time_seconds": sum(r["wall_time_seconds"] for r in rows) / n if n else None,
            "tokens_per_success": sum(r["total_tokens"] for r in rows) / successes if successes else None,
        }

    @staticmethod
    def _differences(problem_summary: dict[str, Any]) -> dict[str, Any]:
        rates: dict[str, list[float]] = {condition: [] for condition in CONDITIONS}
        per_problem: dict[str, Any] = {}
        for problem_id, conditions in problem_summary.items():
            row = {condition: conditions[condition]["ac_rate"] for condition in CONDITIONS}
            if any(value is None for value in row.values()):
                continue
            for condition, value in row.items():
                rates[condition].append(value)
            per_problem[problem_id] = {
                "critical_minus_naive": row["critical_ff"] - row["naive_ff"],
                "naive_minus_baseline": row["naive_ff"] - row["baseline"],
                "critical_minus_baseline": row["critical_ff"] - row["baseline"],
                "critical_minus_gg": row["critical_ff"] - row["general_guidance"],
                "union_ff_minus_baseline": max(row["naive_ff"], row["critical_ff"]) - row["baseline"],
            }
        macro = {condition: sum(values) / len(values) for condition, values in rates.items()}
        return {
            "macro_ac_rates": macro,
            "primary_critical_minus_naive": macro["critical_ff"] - macro["naive_ff"],
            "naive_minus_baseline": macro["naive_ff"] - macro["baseline"],
            "critical_minus_baseline": macro["critical_ff"] - macro["baseline"],
            "critical_minus_gg": macro["critical_ff"] - macro["general_guidance"],
            "union_ff_minus_baseline": sum(
                value["union_ff_minus_baseline"] for value in per_problem.values()
            ) / len(per_problem),
            "per_problem_differences": per_problem,
        }

    def _write_csv(self, records: list[dict[str, Any]]) -> None:
        assert self.run_dir is not None
        fields = sorted(set().union(*(row.keys() for row in records)))
        path = self.run_dir / "results.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fields)
            writer.writeheader()
            for row in records:
                writer.writerow({key: json.dumps(value, ensure_ascii=False)
                                 if isinstance(value, (list, dict)) else value
                                 for key, value in row.items()})

    def _build_blinded_package(self, records: list[dict[str, Any]]) -> None:
        assert self.run_dir is not None
        labels = ["Condition A", "Condition B", "Condition C", "Condition D"]
        shuffled = labels[:]
        random.Random(sha256_text(self.run_dir.name)).shuffle(shuffled)
        mapping = dict(zip(CONDITIONS, shuffled))
        write_json(self.run_dir / "condition_blinding_key.json", mapping)
        package = self.run_dir / "blinded_mechanism_analysis"
        write_json(package / "annotation_schema.json", {
            key: None for key in (
                "ff_claim_adoption", "ff_error_adoption", "audit_quality",
                "planning_final_consistency", "correct_algorithm_family",
                "correct_state_invariant", "implementation_fidelity",
            )
        })
        for problem_id in PROBLEM_IDS:
            source = self.snapshot_root / "materials" / problem_id
            target = package / problem_id / "fixed_source"
            for name in ("formatted_problem.md", "teacher_planning.md", "teacher_final.md",
                         "teacher_code.py", "failure_frontier.md", "general_guidance.md"):
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target / name)
        for row in records:
            cell = self.run_dir / "cells" / row["cell_id"]
            blinded_id = f"{row['problem_id']}__{mapping[row['condition']]}__r{row['replicate_index']:02d}"
            target = package / row["problem_id"] / "samples" / blinded_id
            target.mkdir(parents=True, exist_ok=True)
            for source_name, target_name in (
                ("planning/content.md", "planning.md"),
                ("final/content.md", "final.md"),
                ("submission.py", "submission.py"),
            ):
                path = cell / source_name
                if path.is_file():
                    shutil.copyfile(path, target / target_name)
            write_json(target / "record.json", {
                "sample_id": blinded_id,
                "problem_id": row["problem_id"],
                "condition_label": mapping[row["condition"]],
                "replicate_index": row["replicate_index"],
                "verdict": row["judge_verdict"],
                "annotation": {key: None for key in (
                    "ff_claim_adoption", "ff_error_adoption", "audit_quality",
                    "planning_final_consistency", "correct_algorithm_family",
                    "correct_state_invariant", "implementation_fidelity",
                )},
            })

    def _integrity(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        assert self.run_dir is not None
        cells = [row["cell_id"] for row in records]
        naive_hashes = defaultdict(set)
        critical_hashes = defaultdict(set)
        for row in records:
            if row["condition"] == "naive_ff":
                naive_hashes[row["problem_id"]].add(row["material_hash"])
            if row["condition"] == "critical_ff":
                critical_hashes[row["problem_id"]].add(row["material_hash"])
        material_equal = all(
            naive_hashes[problem_id] == critical_hashes[problem_id]
            and len(naive_hashes[problem_id]) == 1 for problem_id in PROBLEM_IDS
        )
        snapshot = verify_fixed_material_snapshot(self.snapshot_root, self.project_root)
        preflight = read_json(self.run_dir / "preflight_manifest.json")
        prompt_unchanged = all(
            sha256_file(self.project_root / self.config["prompts_dir"] / name) == digest
            for name, digest in preflight["prompt_hashes"].items()
        )
        config_unchanged = sha256_file(self.config_path) == preflight["config_sha256"]
        git = self._git_identity()
        baseline_checks = self.verify_preconditions()
        key = os.environ.get(self.model_config.api_key_env, "")
        secret_hits = 0
        authorization_hits = 0
        for path in self.run_dir.rglob("*"):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if key and key.encode("utf-8") in data:
                secret_hits += 1
            lowered = data.lower()
            if b"authorization:" in lowered or b'"authorization"' in lowered:
                authorization_hits += 1
        return {
            "passed": len(records) == 280 and len(set(cells)) == 280 and material_equal
                      and snapshot["passed"] and prompt_unchanged and config_unchanged
                      and git["commit"] == preflight["git_commit"]
                      and git["working_tree_clean"] and secret_hits == 0
                      and authorization_hits == 0,
            "planned_cells": 280,
            "recorded_cells": len(records),
            "unique_cells": len(set(cells)),
            "extra_samples": len(records) - 280,
            "resampling_count": 0,
            "naive_critical_material_byte_hash_equal": material_equal,
            "fixed_material_verification": snapshot,
            "prompt_hashes_unchanged": prompt_unchanged,
            "config_hash_unchanged": config_unchanged,
            "git_commit_unchanged": git["commit"] == preflight["git_commit"],
            "working_tree_clean": git["working_tree_clean"],
            "baseline_v3_passed": baseline_checks["baseline_v3"]["passed"],
            "expanded_baseline_passed": baseline_checks["expanded_baseline"]["passed"],
            "api_key_value_hits": secret_hits,
            "authorization_header_hits": authorization_hits,
            "api_key_persisted": secret_hits > 0,
            "authorization_header_persisted": authorization_hits > 0,
        }

    def _artifact_hashes(self) -> None:
        assert self.run_dir is not None
        records = []
        for path in sorted(self.run_dir.rglob("*")):
            if path.is_file() and path.name != "artifact_sha256.json":
                records.append({
                    "path": path.relative_to(self.run_dir).as_posix(),
                    "sha256": sha256_file(path),
                })
        write_json(self.run_dir / "artifact_sha256.json", records)

    @staticmethod
    def _summary_markdown(summary: dict[str, Any]) -> str:
        lines = [
            "# Fixed-Material Repeated Student Experiment v1",
            "",
            f"Valid cells: {summary['valid_cells']}/{summary['planned_cells']}",
            f"Model calls: {summary['model_calls']}",
            f"Judge submissions: {summary['judge_submissions']}",
            f"Total tokens: {summary['total_tokens']}",
            "",
            "## Condition Results",
            "",
        ]
        for condition, data in summary["condition_summary"].items():
            lines.append(
                f"- {condition}: {data['successes']}/{data['denominator']} "
                f"({data['micro_ac_rate']:.3f})"
            )
        lines += [
            "", "## Primary Estimand", "",
            "Critical FF - Naive FF macro AC difference: " +
            f"{summary['estimands']['primary_critical_minus_naive']:.3f}",
            "", "This is an exploratory seven-problem fixed-material experiment.",
        ]
        return "\n".join(lines) + "\n"

    def _verify_locked_preflight(self, preflight: dict[str, Any]) -> None:
        if preflight["config_sha256"] != sha256_file(self.config_path):
            raise RuntimeError("config changed since preflight")
        if preflight["fixed_material_manifest_sha256"] != sha256_file(
            self.snapshot_root / "fixed_material_manifest.json"
        ):
            raise RuntimeError("fixed material manifest changed since preflight")
        for name, expected in preflight["prompt_hashes"].items():
            if sha256_file(self.project_root / self.config["prompts_dir"] / name) != expected:
                raise RuntimeError("prompt changed since preflight")
        git = self._git_identity()
        if (git["commit"] != preflight["git_commit"] or
                self.mode == "live" and not git["working_tree_clean"]):
            raise RuntimeError("HEAD or working tree changed since preflight")

    def _git_identity(self) -> dict[str, Any]:
        def command(*args: str) -> str:
            return subprocess.check_output(
                ["git", *args], cwd=self.project_root, text=True
            ).strip()
        return {
            "commit": command("rev-parse", "HEAD"),
            "tags": command("tag", "--points-at", "HEAD").splitlines(),
            "working_tree_clean": command("status", "--short") == "",
        }


def _wilson(successes: int, total: int) -> list[float]:
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [center - margin, center + margin]
