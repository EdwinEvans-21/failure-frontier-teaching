from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess

from experiments.pilot.config import load_config
from experiments.pilot.model_client import ModelInfrastructureError
from experiments.pilot.provenance_ff import FLAT_PAYLOAD_RENDERER_VERSION
from experiments.pilot.storage import read_json, write_json
from ffjudge.models import ProblemSpec

from .adapter import LineagePilotAdapter
from .config import COMPARISON_V2_CONDITIONS, IterativeConfig
from .runner import IterativeRunner
from .roots import file_hash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FreshTeacherConfig:
    base_pilot_config: str
    output_root: str
    teacher_repeats: int
    max_generations: int
    conditions: tuple[str, ...]
    parallel_workers: int
    mode: str
    source_path: str

    @property
    def sha256(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def load_fresh_teacher_config(path: str | Path) -> FreshTeacherConfig:
    source = Path(path).resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    config = FreshTeacherConfig(
        base_pilot_config=data["base_pilot_config"],
        output_root=data["output_root"],
        teacher_repeats=int(data["teacher_repeats"]),
        max_generations=int(data["max_generations"]),
        conditions=tuple(data["conditions"]),
        parallel_workers=int(data.get("parallel_workers", 1)),
        mode=data.get("mode", "dry-run"),
        source_path=str(source),
    )
    if config.teacher_repeats != 5:
        raise ValueError("fresh full experiment requires exactly five Teachers")
    if config.max_generations != 5:
        raise ValueError("fresh full experiment requires five lineage generations")
    if config.conditions != COMPARISON_V2_CONDITIONS:
        raise ValueError("fresh full experiment requires the frozen v2 comparison")
    if config.mode not in {"dry-run", "live"}:
        raise ValueError("mode must be dry-run or live")
    if config.parallel_workers < 1:
        raise ValueError("parallel_workers must be positive")
    return config


class FreshTeacherLineageRunner:
    def __init__(
        self, config: FreshTeacherConfig, *, project_root: Path,
        model: Any | None = None, judge: Any | None = None,
        image_id: str = "unresolved",
        judge_policy: str = "legacy_ffjudge_v1",
    ) -> None:
        self.config = config
        self.project_root = project_root.resolve()
        self.base_path = (self.project_root / config.base_pilot_config).resolve()
        self.base = load_config(self.base_path)
        self.model = model
        self.judge = judge
        self.image_id = image_id
        self.judge_policy = judge_policy
        self.run_dir: Path | None = None

    def dry_run(self, run_id: str) -> dict[str, Any]:
        result = {
            "run_id": run_id, "mode": "dry-run", "api_accessed": False,
            "judge_accessed": False, "problem_count": len(self.base.problems),
            "teacher_repeats": self.config.teacher_repeats,
            "teacher_samples": len(self.base.problems) * self.config.teacher_repeats,
            "max_generations": self.config.max_generations,
            "conditions": list(self.config.conditions),
            "parallel_workers": self.config.parallel_workers,
            "parallel_scheduler": "thread_pool_ordered_map_v1",
            "judge_policy": self.judge_policy,
            "teacher_ac_policy": "skip_all_student_conditions",
            "teacher_failure_policy": "one_lineage_per_condition_stop_on_ac",
        }
        out = Path(self.config.output_root).resolve() / run_id
        write_json(out / "dry_run_plan.json", result)
        return result

    def run(self, run_id: str) -> dict[str, Any]:
        if self.config.mode == "dry-run":
            return self.dry_run(run_id)
        if self.model is None or self.judge is None:
            raise ValueError("live mode requires model and judge")
        self.run_dir = Path(self.config.output_root).resolve() / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._freeze_manifest(run_id)
        source = self.run_dir / "fresh_teacher_source"
        root_ids: list[str] = []
        teacher_rows: list[dict[str, Any]] = []
        tasks = []
        for repeat in range(self.config.teacher_repeats):
            for item in self.base.problems:
                spec = ProblemSpec.load(self.project_root / item.problem)
                tasks.append((repeat, item, spec, f"{run_id}-t{repeat:02d}-{spec.problem_id}"))

        def sample(task: tuple[int, Any, ProblemSpec, str]) -> dict[str, Any]:
            repeat, item, spec, episode_id = task
            adapter = LineagePilotAdapter(self.base, self.model, judge=self.judge,
                                         project_root=self.project_root)
            return self._sample_teacher(adapter, source, episode_id, repeat, item, spec)

        with ThreadPoolExecutor(max_workers=self.config.parallel_workers,
                                thread_name_prefix="fft-teacher") as executor:
            for row in executor.map(sample, tasks):
                teacher_rows.append(row)
                if row["lineage_root_eligible"]:
                    root_ids.append(row["source_episode_id"])
                write_json(self.run_dir / "teacher_results.json", teacher_rows)
        failure_roots = [x for x in teacher_rows if x["teacher_verdict"] != "AC"]
        write_json(self.run_dir / "teacher_summary.json", {
            "teacher_samples": len(teacher_rows),
            "teacher_ac": sum(x["teacher_verdict"] == "AC" for x in teacher_rows),
            "teacher_failures": len(failure_roots),
            "lineage_root_eligible": len(root_ids),
            "lineage_root_ineligible": sum(
                x["teacher_verdict"] != "AC" and not x["lineage_root_eligible"]
                for x in teacher_rows),
            "rows": teacher_rows,
        })
        if not root_ids:
            aggregate = {
                "status": "not_started_no_teacher_failures",
                "lineages_total": 0,
                "configured_conditions": list(self.config.conditions),
            }
            result = {
                "run_id": run_id, "finished_at": _now(),
                "teacher_samples": len(teacher_rows),
                "teacher_ac": len(teacher_rows), "teacher_failures": 0,
                "lineage_root_eligible": 0,
                "lineage_aggregate": aggregate,
            }
            write_json(self.run_dir / "full_experiment_summary.json", result)
            return result
        iterative = IterativeConfig(
            schema_version="1.0",
            experiment_policy="minimal_failure_lineage_v1",
            base_pilot_config=str(self.base_path),
            source_run_dir=str(source), root_episode_ids=tuple(root_ids),
            output_root=str(self.run_dir / "lineage_stage"),
            max_generations=self.config.max_generations,
            lineage_repeats=1, stop_on_ac=True,
            condition_order_policy="balanced_rotation_v1",
            conditions=self.config.conditions, mode="live",
            source_path=self.config.source_path,
            parallel_workers=self.config.parallel_workers,
        )
        aggregate = IterativeRunner(
            iterative, project_root=self.project_root, model=self.model,
            judge=self.judge, image_id=self.image_id,
        ).run("teacher-failure-lineages")
        result = {
            "run_id": run_id, "finished_at": _now(),
            "teacher_samples": len(teacher_rows),
            "teacher_ac": sum(x["teacher_verdict"] == "AC" for x in teacher_rows),
            "teacher_failures": len(failure_roots),
            "lineage_root_eligible": len(root_ids),
            "lineage_aggregate": aggregate,
        }
        write_json(self.run_dir / "full_experiment_summary.json", result)
        return result

    def _freeze_manifest(self, run_id: str) -> None:
        assert self.run_dir is not None
        path = self.run_dir / "fresh_experiment_manifest.json"
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.strip()
        manifest = {
            "schema_version": "1.0", "run_id": run_id,
            "created_at": _now(), "git_commit": commit,
            "config_sha256": self.config.sha256,
            "base_config_sha256": file_hash(self.base_path),
            "baseline_id": self.base.baseline_id,
            "baseline_manifest": self.base.baseline_manifest,
            "baseline_manifest_sha256": file_hash(
                self.project_root / self.base.baseline_manifest),
            "problem_count": len(self.base.problems),
            "teacher_repeats": self.config.teacher_repeats,
            "teacher_samples": len(self.base.problems) * self.config.teacher_repeats,
            "max_generations": self.config.max_generations,
            "conditions": list(self.config.conditions),
            "parallel_workers": self.config.parallel_workers,
            "parallel_scheduler": "thread_pool_ordered_map_v1",
            "sandbox_image_id": self.image_id,
            "judge_policy": self.judge_policy,
        }
        if path.is_file():
            saved = read_json(path)
            manifest["created_at"] = saved["created_at"]
            if saved != manifest:
                raise ValueError("fresh experiment manifest drift")
        else:
            write_json(path, manifest)

    def _sample_teacher(
        self, adapter: LineagePilotAdapter, source: Path, episode_id: str,
        repeat: int, item: Any, spec: ProblemSpec,
    ) -> dict[str, Any]:
        episode = source / "episodes" / episode_id
        problem_dir = episode / "problems" / spec.problem_id
        record_path = problem_dir / "record.json"
        if record_path.is_file():
            return read_json(record_path)["fresh_teacher_root"]
        write_json(episode / "config.snapshot.yaml", read_json(self.base_path))
        problem = adapter.renderer.formatted_problem(
            self.project_root / item.problem,
            self.project_root / item.public_tests,
        )
        try:
            teacher = adapter._solver_stage(
                problem_dir / "teacher", "teacher", spec.problem_id,
                "teacher", problem, item, spec,
            )
        except ModelInfrastructureError:
            raise
        verdict = teacher["verdict"]
        provenance_ok = False
        provenance_error = None
        if verdict not in {"AC", "JUDGE_ERROR"} and teacher.get("code"):
            try:
                adapter._provenance_failure_material(
                    problem_dir, spec.problem_id, problem, teacher)
                provenance_ok = True
            except Exception as error:
                if isinstance(error, (OSError, ModelInfrastructureError)):
                    raise
                provenance_error = f"{type(error).__name__}:{error}"
        eligible = (
            verdict not in {"AC", "JUDGE_ERROR"}
            and bool(teacher.get("code")) and provenance_ok
        )
        row = {
            "source_episode_id": episode_id,
            "problem_id": spec.problem_id,
            "teacher_repeat_index": repeat,
            "teacher_verdict": verdict,
            "teacher_code_extracted": bool(teacher.get("code")),
            "provenance_ready": provenance_ok,
            "provenance_error": provenance_error,
            "lineage_root_eligible": eligible,
            "teacher_ac_students_skipped": verdict == "AC",
        }
        provenance = problem_dir / "teaching_materials/provenance_ff_v2"
        flat = provenance / "flat_failure_payload.txt"
        record = {
            "run_id": episode_id, "problem_id": spec.problem_id,
            "teacher": {
                "verdict": verdict,
                "final_code_extracted": bool(teacher.get("code")),
            },
            "valid_episode": verdict != "JUDGE_ERROR" and (
                verdict == "AC" or eligible),
            "branch": "teacher_success" if verdict == "AC" else "teacher_failure",
            "provenance_failure_frontier": ({
                "flat_payload_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
                "flat_payload_sha256": file_hash(flat),
            } if provenance_ok else {}),
            "fresh_teacher_root": row,
        }
        write_json(record_path, record)
        return row
