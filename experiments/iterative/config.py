from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import json


POLICY = "minimal_failure_lineage_v1"
INDEPENDENT_RESTART_CONDITION = "independent_restart_v1"
CODE_VERDICT_CONDITION = "code_verdict_chain_v1"
FLAT_V1_CONDITION = "code_verdict_flat_ff_chain_v1"
CONDITIONS = (
    INDEPENDENT_RESTART_CONDITION,
    CODE_VERDICT_CONDITION,
    FLAT_V1_CONDITION,
)
FLAT_V2_CONDITION = "code_verdict_flat_ff_chain_v2"
FLAT_V2_CONDITIONS = (FLAT_V2_CONDITION,)
COMPARISON_V2_CONDITIONS = (
    INDEPENDENT_RESTART_CONDITION,
    CODE_VERDICT_CONDITION,
    FLAT_V2_CONDITION,
)
REGISTERED_CONDITION_SETS = {
    CONDITIONS,
    FLAT_V2_CONDITIONS,
    COMPARISON_V2_CONDITIONS,
}


@dataclass(frozen=True)
class IterativeConfig:
    schema_version: str
    experiment_policy: str
    base_pilot_config: str
    source_run_dir: str
    root_episode_ids: tuple[str, ...]
    output_root: str
    max_generations: int
    lineage_repeats: int
    stop_on_ac: bool
    condition_order_policy: str
    conditions: tuple[str, ...]
    mode: str
    source_path: str
    parallel_workers: int = 1
    teacher_ac_episode_ids: tuple[str, ...] = ()
    source_problem_count: int | None = None

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def sha256(self) -> str:
        raw = json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def load_iterative_config(path: str | Path) -> IterativeConfig:
    source = Path(path).resolve()
    text = source.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import yaml  # type: ignore[import-not-found]
        data = yaml.safe_load(text)
    config = IterativeConfig(
        schema_version=str(data["schema_version"]),
        experiment_policy=data["experiment_policy"],
        base_pilot_config=data["base_pilot_config"],
        source_run_dir=data["source_run_dir"],
        root_episode_ids=tuple(data["root_episode_ids"]),
        output_root=data["output_root"],
        max_generations=int(data["max_generations"]),
        lineage_repeats=int(data["lineage_repeats"]),
        stop_on_ac=bool(data["stop_on_ac"]),
        condition_order_policy=data["condition_order_policy"],
        conditions=tuple(data["conditions"]),
        mode=data.get("mode", "dry-run"),
        source_path=str(source),
        parallel_workers=int(data.get("parallel_workers", 1)),
        teacher_ac_episode_ids=tuple(data.get("teacher_ac_episode_ids", ())),
        source_problem_count=(
            int(data["source_problem_count"])
            if data.get("source_problem_count") is not None else None),
    )
    if config.experiment_policy != POLICY:
        raise ValueError(f"experiment_policy must be {POLICY}")
    if config.conditions not in REGISTERED_CONDITION_SETS:
        raise ValueError(
            "conditions must be a registered frozen condition set")
    if config.condition_order_policy != "balanced_rotation_v1":
        raise ValueError("condition_order_policy must be balanced_rotation_v1")
    if config.mode not in {"dry-run", "mock", "live"}:
        raise ValueError("mode must be dry-run, mock, or live")
    if config.max_generations < 1 or config.lineage_repeats < 1:
        raise ValueError("generation and repeat counts must be positive")
    if config.parallel_workers < 1:
        raise ValueError("parallel_workers must be positive")
    if not config.stop_on_ac:
        raise ValueError("minimal_failure_lineage_v1 requires stop_on_ac")
    if not config.root_episode_ids or len(set(config.root_episode_ids)) != len(config.root_episode_ids):
        raise ValueError("root_episode_ids must be nonempty and unique")
    if len(set(config.teacher_ac_episode_ids)) != len(config.teacher_ac_episode_ids):
        raise ValueError("teacher_ac_episode_ids must be unique")
    if set(config.root_episode_ids) & set(config.teacher_ac_episode_ids):
        raise ValueError("Teacher-failure roots and Teacher-AC skips must be disjoint")
    if (config.source_problem_count is not None and
            len(config.root_episode_ids) + len(config.teacher_ac_episode_ids) !=
            config.source_problem_count):
        raise ValueError("source problem count differs from frozen Teacher split")
    return config


def resolve_from_project(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()
