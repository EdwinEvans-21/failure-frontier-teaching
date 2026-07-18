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
    expected_problem_count = (
        31 if config.baseline_id == "failure-frontier-baseline-v3-expanded"
        else 5
    )
    if len(config.problems) != expected_problem_count:
        raise ValueError(
            f"configured baseline requires exactly {expected_problem_count} problems"
        )
