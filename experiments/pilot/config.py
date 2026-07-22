from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model_name: str
    reasoning_mode: bool
    temperature: float
    top_p: float
    max_output_tokens: int
    base_url: str
    api_key_env: str
    seed: int | None
    network_retry_limit: int
    network_retry_backoff_seconds: float
    mock_responses_path: str | None = None
    tokenizer_name: str | None = None
    tokenizer_revision: str | None = None
    thinking: dict[str, str] | None = None


@dataclass(frozen=True)
class TeachingMaterialConfig:
    token_match_tolerance: float
    gg_generation_policy: str
    failure_frontier_max_output_tokens: int
    gg_blueprint_max_output_tokens: int
    gg_blueprint_repair_attempts: int
    gg_material_max_output_tokens: int
    gg_material_revision_attempts: int
    gg_short_expand_overshoot_factor: float
    gg_min_expand_scale: float
    gg_max_expand_scale: float
    gg_acceptance_policy: str = "token_interval_v1"


@dataclass(frozen=True)
class SolverConfig:
    protocol: str
    planning_max_output_tokens: int
    final_max_output_tokens: int


@dataclass(frozen=True)
class ExecutionConfig:
    output_root: str
    judge_image: str
    judge_phase: str
    resume: bool


@dataclass(frozen=True)
class ProblemConfig:
    problem: str
    public_tests: str
    hidden_tests: str


@dataclass(frozen=True)
class PilotConfig:
    schema_version: str
    baseline_id: str
    baseline_manifest: str
    mode: str
    model: ModelConfig
    solver: SolverConfig
    teaching_material: TeachingMaterialConfig
    execution: ExecutionConfig
    problems: tuple[ProblemConfig, ...]
    prompts_dir: str
    student_conditions: tuple[str, ...] = (
        "success_only",
        "failure_frontier",
        "general_guidance",
    )
    source_path: str | None = None
    failure_frontier_policy: str = "legacy_failure_frontier_v1"
    teacher_failure_analysis_policy: str = "disabled_legacy"
    direct_ff_policy: str = "legacy_naive_ff_v1"
    critical_ff_policy: str = "critical_ff_v1"
    rigorous_review_ff_policy: str = "disabled_legacy"
    flat_ff_policy: str = "disabled_legacy"
    baseline_policy: str = "legacy_public_problem_only"
    shared_failure_payload_builder: str = "legacy_unstructured_payload_v1"

    def public_snapshot(self) -> dict[str, Any]:
        data = _as_dict(self)
        # Secrets are never accepted in config; only the environment variable name
        # is persisted. Keep this explicit in case the schema grows later.
        data["model"].pop("api_key", None)
        return data


def _as_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _as_dict(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, tuple):
        return [_as_dict(item) for item in value]
    return value


def _load_yaml_compatible(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as json_error:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as error:
            raise ValueError(
                "config must use JSON-compatible YAML unless PyYAML is installed"
            ) from json_error
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("pilot config must be an object")
    if "api_key" in data.get("model", {}):
        raise ValueError("API keys must come from model.api_key_env, not config")
    return data


def load_config(path: str | Path) -> PilotConfig:
    config_path = Path(path).resolve()
    data = _load_yaml_compatible(config_path)
    model = ModelConfig(**data["model"])
    solver = SolverConfig(**data["solver"])
    teaching = TeachingMaterialConfig(**data["teaching_material"])
    execution = ExecutionConfig(**data["execution"])
    problems = tuple(ProblemConfig(**item) for item in data["problems"])
    config = PilotConfig(
        schema_version=str(data["schema_version"]),
        baseline_id=data["baseline_id"],
        baseline_manifest=data["baseline_manifest"],
        mode=data.get("mode", "live"),
        model=model,
        solver=solver,
        teaching_material=teaching,
        execution=execution,
        problems=problems,
        prompts_dir=data["prompts_dir"],
        student_conditions=tuple(data.get("student_conditions", (
            "success_only",
            "failure_frontier",
            "general_guidance",
        ))),
        source_path=str(config_path),
        failure_frontier_policy=data.get(
            "failure_frontier_policy", "legacy_failure_frontier_v1"),
        teacher_failure_analysis_policy=data.get(
            "teacher_failure_analysis_policy", "disabled_legacy"),
        direct_ff_policy=data.get("direct_ff_policy", "legacy_naive_ff_v1"),
        critical_ff_policy=data.get("critical_ff_policy", "critical_ff_v1"),
        rigorous_review_ff_policy=data.get(
            "rigorous_review_ff_policy", "disabled_legacy"),
        flat_ff_policy=data.get("flat_ff_policy", "disabled_legacy"),
        baseline_policy=data.get("baseline_policy", "legacy_public_problem_only"),
        shared_failure_payload_builder=data.get(
            "shared_failure_payload_builder", "legacy_unstructured_payload_v1"),
    )
    _validate(config)
    return config


def _validate(config: PilotConfig) -> None:
    if config.mode not in {"live", "mock", "dry-run", "api-check", "smoke-test"}:
        raise ValueError("mode must be live, mock, dry-run, api-check, or smoke-test")
    if config.model.reasoning_mode:
        raise ValueError("pilot v1 requires non-reasoning mode")
    if config.model.thinking != {"type": "disabled"}:
        raise ValueError("non-reasoning mode requires thinking.type=disabled")
    if not config.model.model_name:
        raise ValueError("model.model_name must be configured")
    if config.model.max_output_tokens <= 0:
        raise ValueError("model.max_output_tokens must be positive")
    if config.solver.protocol != "two_stage_v1":
        raise ValueError("solver.protocol must be two_stage_v1")
    if config.solver.planning_max_output_tokens <= 0:
        raise ValueError("planning_max_output_tokens must be positive")
    if config.solver.final_max_output_tokens <= 0:
        raise ValueError("final_max_output_tokens must be positive")
    if not 0 <= config.model.temperature <= 2:
        raise ValueError("model.temperature must be between 0 and 2")
    if not 0 < config.model.top_p <= 1:
        raise ValueError("model.top_p must be in (0, 1]")
    if not 0 <= config.teaching_material.token_match_tolerance < 1:
        raise ValueError("token_match_tolerance must be in [0, 1)")
    if config.teaching_material.gg_generation_policy != "blueprint_render_v1":
        raise ValueError("gg_generation_policy must be blueprint_render_v1")
    if config.teaching_material.gg_acceptance_policy not in {
        "token_interval_v1", "semantic_complete_no_length_v2"
    }:
        raise ValueError("unsupported gg_acceptance_policy")
    if config.teaching_material.failure_frontier_max_output_tokens <= 0:
        raise ValueError("failure_frontier_max_output_tokens must be positive")
    if config.teaching_material.gg_blueprint_max_output_tokens <= 0:
        raise ValueError("gg_blueprint_max_output_tokens must be positive")
    if config.teaching_material.gg_blueprint_repair_attempts != 1:
        raise ValueError("gg_blueprint_repair_attempts must be exactly 1")
    if config.teaching_material.gg_material_max_output_tokens <= 0:
        raise ValueError("gg_material_max_output_tokens must be positive")
    if config.teaching_material.gg_material_revision_attempts != 2:
        raise ValueError("gg_material_revision_attempts must be exactly 2")
    if config.teaching_material.gg_short_expand_overshoot_factor <= 1:
        raise ValueError("gg_short_expand_overshoot_factor must be greater than 1")
    if config.teaching_material.gg_min_expand_scale < 1:
        raise ValueError("gg_min_expand_scale must be at least 1")
    if (config.teaching_material.gg_max_expand_scale <
            config.teaching_material.gg_min_expand_scale):
        raise ValueError("gg_max_expand_scale must be at least gg_min_expand_scale")
    if config.execution.judge_phase != "hidden":
        raise ValueError("pilot v1 formal submissions must use the hidden phase")
    allowed_student_conditions = {
        "success_only",
        "failure_frontier",
        "critical_failure_frontier",
        "general_guidance",
        "baseline",
        "direct_ff_v2",
        "critical_ff_v2",
        "rigorous_review_ff_v3",
        "flat_ff_v2",
    }
    if len(config.student_conditions) != len(set(config.student_conditions)):
        raise ValueError("student_conditions must be unique")
    if not set(config.student_conditions) <= allowed_student_conditions:
        raise ValueError("student_conditions contains an unsupported condition")
    from .provenance_ff import (
        BASELINE_POLICY, CRITICAL_FF_POLICY, DIRECT_FF_POLICY, FLAT_FF_POLICY,
        FAILURE_FRONTIER_POLICY, SHARED_PAYLOAD_BUILDER_VERSION,
        RIGOROUS_REVIEW_FF_POLICY, TEACHER_FAILURE_ANALYSIS_POLICY,
    )
    review_condition = (
        "rigorous_review_ff_v3"
        if "rigorous_review_ff_v3" in config.student_conditions
        else "critical_ff_v2"
    )
    v2_conditions = {"baseline", "direct_ff_v2", review_condition,
                     "flat_ff_v2", "general_guidance"}
    using_v2 = bool(set(config.student_conditions) &
                    {"baseline", "direct_ff_v2", "critical_ff_v2",
                     "rigorous_review_ff_v3", "flat_ff_v2"})
    required_student_conditions = (
        v2_conditions if using_v2
        else {"success_only", "failure_frontier", "general_guidance"}
    )
    if not required_student_conditions <= set(config.student_conditions):
        raise ValueError(
            "student_conditions do not contain the complete selected treatment set"
        )
    if using_v2:
        policies = {
            "failure_frontier_policy": (
                config.failure_frontier_policy, FAILURE_FRONTIER_POLICY),
            "teacher_failure_analysis_policy": (
                config.teacher_failure_analysis_policy,
                TEACHER_FAILURE_ANALYSIS_POLICY),
            "direct_ff_policy": (config.direct_ff_policy, DIRECT_FF_POLICY),
            "flat_ff_policy": (config.flat_ff_policy, FLAT_FF_POLICY),
            "baseline_policy": (config.baseline_policy, BASELINE_POLICY),
            "shared_failure_payload_builder": (
                config.shared_failure_payload_builder,
                SHARED_PAYLOAD_BUILDER_VERSION),
        }
        drift = [name for name, (actual, expected) in policies.items()
                 if actual != expected]
        if review_condition == "rigorous_review_ff_v3":
            if config.rigorous_review_ff_policy != RIGOROUS_REVIEW_FF_POLICY:
                drift.append("rigorous_review_ff_policy")
            if config.critical_ff_policy not in {"critical_ff_v1", "disabled_legacy"}:
                drift.append("critical_ff_policy")
        elif config.critical_ff_policy != CRITICAL_FF_POLICY:
            drift.append("critical_ff_policy")
        if drift:
            raise ValueError("v2 conditions require explicit v2 policies: " +
                             ", ".join(drift))
        if (config.teaching_material.gg_acceptance_policy !=
                "semantic_complete_no_length_v2"):
            raise ValueError(
                "provenance v2 requires semantic_complete_no_length_v2 GG acceptance")
    elif (config.critical_ff_policy == CRITICAL_FF_POLICY or
          config.rigorous_review_ff_policy == RIGOROUS_REVIEW_FF_POLICY or
          any(value.endswith("_v2") for value in (
            config.failure_frontier_policy,
            config.teacher_failure_analysis_policy, config.direct_ff_policy,
            config.flat_ff_policy,
            config.baseline_policy, config.shared_failure_payload_builder))):
        raise ValueError("v2 policies cannot be paired with legacy conditions")
    elif config.teaching_material.gg_acceptance_policy != "token_interval_v1":
        raise ValueError("legacy conditions require token_interval_v1 GG acceptance")
    expected_problem_count = {
        "failure-frontier-baseline-v3-expanded": 31,
        "failure-frontier-baseline-v4-100-lc-snapshot": 100,
        "failure-frontier-baseline-v4-100-lc-independent-audit-v2": 100,
    }.get(config.baseline_id, 5)
    if len(config.problems) != expected_problem_count:
        raise ValueError(
            f"configured baseline requires exactly {expected_problem_count} problems"
        )
