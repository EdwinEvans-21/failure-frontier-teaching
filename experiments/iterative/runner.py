from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
from difflib import SequenceMatcher
import subprocess
from concurrent.futures import ThreadPoolExecutor

from experiments.pilot.model_client import ModelInfrastructureError
from experiments.pilot.provenance_ff import FLAT_PAYLOAD_RENDERER_VERSION
from experiments.pilot.storage import read_json, write_json, write_text
from ffjudge.models import ProblemSpec

from .adapter import LineagePilotAdapter
from .aggregation import aggregate_run, parse_lineage_manifests, write_reports
from .config import (
    CODE_VERDICT_CONDITION, CONDITIONS, FLAT_V1_CONDITION,
    FLAT_V2_CONDITION, INDEPENDENT_RESTART_CONDITION, IterativeConfig,
    resolve_from_project,
)
from .flat_addon import (
    LINEAGE_FLAT_ADDON_RENDERER_VERSION,
    audit_addon_excludes_complete_sources, render_lineage_flat_analysis,
)
from .payloads import (
    ParentMaterial, audit_direct_parent_payload,
    audit_structured_parent_sources, normalized_code_hash,
    render_inherited_payload, render_inherited_payload_v2, sha256_text,
)
from .roots import (
    canonical_hash, file_hash, find_problem_config, freeze_root,
    locate_episode, validate_root,
)


OUTCOMES = {
    "SOLVED", "COMPLETED_UNSOLVED", "TERMINATED_NO_INHERITABLE_CODE",
    "TERMINATED_FLAT_FF_PROTOCOL_FAILURE", "INVALID_INFRASTRUCTURE",
    "INVALID_INTEGRITY",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def complete_model_visible_payload(problem: str, inherited: str) -> str:
    return (
        problem.rstrip() + "\n\n# Inherited Failure Material\n\n"
        + inherited.rstrip() + "\n"
    )


def condition_rotation(
    root_index: int, repeat_index: int,
    conditions: tuple[str, ...] = CONDITIONS,
) -> tuple[str, ...]:
    shift = (root_index + repeat_index) % len(conditions)
    return conditions[shift:] + conditions[:shift]


class IterativeRunner:
    def __init__(
        self, config: IterativeConfig, *, project_root: str | Path = ".",
        model: Any | None = None, judge: Any | None = None,
        image_id: str = "unresolved", flat_pipeline: Any | None = None,
    ) -> None:
        self.config = config
        self.project_root = Path(project_root).resolve()
        self.base_config_path = resolve_from_project(
            self.project_root, config.base_pilot_config)
        from experiments.pilot.config import load_config
        self.pilot_config = load_config(self.base_config_path)
        self.model = model
        self.judge = judge
        self.image_id = image_id
        self.flat_pipeline = flat_pipeline
        self.run_dir: Path | None = None

    def dry_run(self, run_id: str = "minimal-failure-lineage-dry-run") -> dict[str, Any]:
        output = resolve_from_project(self.project_root, self.config.output_root) / run_id
        output.mkdir(parents=True, exist_ok=True)
        adapter = LineagePilotAdapter(
            self.pilot_config, None, judge=object(), project_root=self.project_root)
        sample_parent = ParentMaterial(
            0, "class Solution:\n    pass", "WA",
            sha256_text("class Solution:\n    pass"), "FLAT_FF_SENTINEL",
            sha256_text("FLAT_FF_SENTINEL"), FLAT_PAYLOAD_RENDERER_VERSION)
        problem = "<FORMATTED_PUBLIC_PROBLEM>"
        calls = {}
        for condition in self.config.conditions:
            if condition == INDEPENDENT_RESTART_CONDITION:
                material = ""
            elif condition == FLAT_V2_CONDITION:
                sample_parent = ParentMaterial(
                    sample_parent.generation, sample_parent.code,
                    sample_parent.verdict, sample_parent.code_sha256,
                    sample_parent.flat_ff, sample_parent.flat_ff_sha256,
                    sample_parent.flat_renderer_version,
                    "<validated-record>", sha256_text("<validated-record>"),
                    "FLAT_ADDON_SENTINEL", "<flat-addon>",
                    sha256_text("FLAT_ADDON_SENTINEL"),
                    LINEAGE_FLAT_ADDON_RENDERER_VERSION,
                )
                material = render_inherited_payload_v2(sample_parent)
            else:
                material = render_inherited_payload(
                    sample_parent, include_flat=condition == FLAT_V1_CONDITION)
            calls[condition] = [adapter._rendered_solver_call(
                stage, "student", "<problem_id>", condition, problem,
                additional_material=material,
                planning_content="<own-planning>", planning_status="<status>")
                for stage in ("planning", "final")]
        result = {
            "experiment_policy": self.config.experiment_policy,
            "mode": "dry-run", "api_accessed": False, "judge_accessed": False,
            "formal_experiment_started": False,
            "source_roots_not_resampled": True,
            "source_problem_count": self.config.source_problem_count,
            "teacher_failure_roots": len(self.config.root_episode_ids),
            "teacher_ac_skipped": len(self.config.teacher_ac_episode_ids),
            "condition_rotations": [list(condition_rotation(
                i, r, self.config.conditions))
                for i, _ in enumerate(self.config.root_episode_ids)
                for r in range(self.config.lineage_repeats)],
            "rendered_calls": calls,
            "flat_ff_pipeline": "PilotRunner._provenance_failure_material",
        }
        write_json(output / "dry_run_plan.json", result)
        return result

    def run(self, run_id: str) -> dict[str, Any]:
        if self.config.mode == "dry-run":
            return self.dry_run(run_id)
        if self.model is None or self.judge is None:
            raise ValueError("mock/live mode requires injected model and judge")
        preflight = self.preflight(run_id)
        roots = preflight["roots"]
        assert self.run_dir is not None
        tasks = [
            (root, root_index, repeat, condition)
            for root_index, root in enumerate(roots)
            for repeat in range(self.config.lineage_repeats)
            for condition in condition_rotation(root_index, repeat, self.config.conditions)
        ]
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers,
                                thread_name_prefix="fft-lineage") as executor:
            summaries = list(executor.map(
                lambda task: self._run_lineage(*task), tasks))
        parsed_manifests = parse_lineage_manifests(self.run_dir)
        aggregate = aggregate_run(
            summaries, self.config.max_generations, self.config.conditions,
            parsed_lineage_manifests=parsed_manifests,
        )
        write_reports(self.run_dir, summaries, aggregate)
        return aggregate

    def preflight(self, run_id: str) -> dict[str, Any]:
        """Freeze and verify roots and run identity without model/Judge access."""
        self.run_dir = resolve_from_project(
            self.project_root, self.config.output_root) / run_id
        self.run_dir.mkdir(parents=True, exist_ok=self.pilot_config.execution.resume)
        root_dir = self.run_dir / "source_roots"
        source_run = resolve_from_project(self.project_root, self.config.source_run_dir)
        teacher_ac_skips = self._validate_teacher_ac_skips(source_run)
        roots = []
        for episode_id in self.config.root_episode_ids:
            path = root_dir / f"{episode_id}.json"
            root = read_json(path) if path.is_file() else freeze_root(
                self.project_root, source_run, episode_id, path,
                require_lineage_flat_addon=(
                    FLAT_V2_CONDITION in self.config.conditions),
            )
            validate_root(root)
            roots.append(root)
        manifest = self._run_manifest(run_id, roots, teacher_ac_skips)
        manifest_path = self.run_dir / "run_manifest.json"
        if manifest_path.is_file():
            saved_manifest = read_json(manifest_path)
            manifest["created_at"] = saved_manifest.get("created_at")
            if saved_manifest != manifest:
                raise ValueError("run manifest drift; resume refused")
        else:
            write_json(manifest_path, manifest)
        result = {
            "run_id": run_id, "run_dir": str(self.run_dir),
            "api_accessed": False, "judge_accessed": False,
            "manifest": manifest, "roots": roots,
            "teacher_ac_skips": teacher_ac_skips,
        }
        write_json(self.run_dir / "preflight_result.json", result)
        return result

    def _validate_teacher_ac_skips(self, source_run: Path) -> list[dict[str, Any]]:
        skips = []
        for episode_id in self.config.teacher_ac_episode_ids:
            episode = locate_episode(source_run, episode_id)
            records = list((episode / "problems").glob("*/record.json"))
            monolithic = episode / "problems" / episode_id / "record.json"
            if monolithic.is_file():
                records = [monolithic]
            if len(records) != 1:
                raise ValueError("Teacher-AC episode must contain one problem record")
            record = read_json(records[0])
            if record.get("teacher", {}).get("verdict") != "AC":
                raise ValueError("configured Teacher-AC skip is not AC")
            skips.append({
                "source_episode_id": episode_id,
                "problem_id": record["problem_id"],
                "record_sha256": file_hash(records[0]),
            })
        return skips

    def _run_manifest(
        self, run_id: str, roots: list[dict[str, Any]],
        teacher_ac_skips: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt_paths = [
            self.project_root / "experiments/prompts/code_verdict_chain_v1.md",
            self.project_root / "experiments/prompts/code_verdict_flat_chain_v1.md",
            self.project_root / "experiments/prompts/solver_planning.md",
            self.project_root / "experiments/prompts/solver_final.md",
            self.project_root / "experiments/prompts/solver_final_user.md",
            self.project_root / "experiments/prompts/baseline_v2.md",
        ]
        if FLAT_V2_CONDITION in self.config.conditions:
            prompt_paths.append(
                self.project_root / "experiments/prompts/code_verdict_flat_chain_v2.md")
        implementation_paths = sorted(
            (self.project_root / "experiments/iterative").glob("*.py")) + [
                self.project_root / "experiments/run_iterative.py"]
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.strip()
        tags = subprocess.run(
            ["git", "tag", "--points-at", "HEAD"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.splitlines()
        dirty = subprocess.run(
            ["git", "status", "--short"], cwd=self.project_root,
            capture_output=True, text=True, check=True).stdout.splitlines()
        return {
            "schema_version": "1.0", "run_id": run_id,
            "experiment_policy": self.config.experiment_policy,
            "git_commit": commit, "git_tags": tags,
            "working_tree_dirty": bool(dirty), "working_tree_status": dirty,
            "config_sha256": self.config.sha256,
            "base_pilot_config_sha256": file_hash(self.base_config_path),
            "source_root_manifest_sha256": [r["root_manifest_sha256"] for r in roots],
            "source_problem_count": self.config.source_problem_count,
            "teacher_failure_root_count": len(roots),
            "teacher_ac_skip_count": len(teacher_ac_skips),
            "teacher_ac_skips": teacher_ac_skips,
            "prompt_sha256": {str(p.relative_to(self.project_root)).replace("\\", "/"): file_hash(p)
                              for p in prompt_paths},
            "implementation_sha256": {
                str(p.relative_to(self.project_root)).replace("\\", "/"): file_hash(p)
                for p in implementation_paths},
            "model": asdict(self.pilot_config.model),
            "solver": asdict(self.pilot_config.solver),
            "sandbox_image_id": self.image_id,
            "conditions": list(self.config.conditions),
            "condition_order_policy": "balanced_rotation_v1",
            "flat_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
            "flat_addon_renderer_version": (
                LINEAGE_FLAT_ADDON_RENDERER_VERSION
                if FLAT_V2_CONDITION in self.config.conditions else None),
            "max_generations": self.config.max_generations,
            "lineage_repeats": self.config.lineage_repeats,
            "stop_on_ac": True,
            "created_at": now(),
        }

    def _run_lineage(self, root: dict[str, Any], root_index: int,
                     repeat: int, condition: str) -> dict[str, Any]:
        assert self.run_dir is not None
        lineage_id = f"{root['source_episode_id']}__r{repeat:02d}__{condition}"
        directory = self.run_dir / "lineages" / lineage_id
        summary_path = directory / "lineage_summary.json"
        manifest = {
            "experiment_policy": self.config.experiment_policy,
            "lineage_id": lineage_id, "condition": condition,
            "problem_id": root["problem_id"],
            "root_episode_id": root["source_episode_id"],
            "root_index": root_index, "lineage_repeat_index": repeat,
            "condition_execution_order": list(condition_rotation(
                root_index, repeat, self.config.conditions)),
            "max_generations": self.config.max_generations,
            "config_sha256": self.config.sha256,
            "source_root_manifest_sha256": root["root_manifest_sha256"],
            "sandbox_image_id": self.image_id,
        }
        manifest_path = directory / "lineage_manifest.json"
        if manifest_path.is_file() and read_json(manifest_path) != manifest:
            return self._invalid_summary(manifest, "INVALID_INTEGRITY", "lineage_manifest_drift")
        write_json(manifest_path, manifest)
        try:
            validate_root(root)
            if summary_path.is_file():
                saved = read_json(summary_path)
                if saved.get("outcome") != "INVALID_INFRASTRUCTURE":
                    self._validate_lineage_links(directory, saved)
                    return saved
            summary = self._execute_generations(directory, manifest, root)
        except ModelInfrastructureError as error:
            summary = self._invalid_summary(manifest, "INVALID_INFRASTRUCTURE", type(error).__name__)
        except OSError as error:
            summary = self._invalid_summary(manifest, "INVALID_INFRASTRUCTURE", type(error).__name__)
        except ValueError as error:
            summary = self._invalid_summary(manifest, "INVALID_INTEGRITY", str(error))
        write_json(summary_path, summary)
        return summary

    def _execute_generations(self, directory: Path, manifest: dict[str, Any],
                             root: dict[str, Any]) -> dict[str, Any]:
        base_config, item = find_problem_config(
            self.base_config_path, root["problem_id"], self.project_root)
        adapter = LineagePilotAdapter(base_config, self.model, judge=self.judge,
                                      project_root=self.project_root)
        spec = ProblemSpec.load(self.project_root / item.problem)
        problem = adapter.renderer.formatted_problem(
            self.project_root / item.problem, self.project_root / item.public_tests)
        artifacts = root["artifacts"]
        is_flat_v2 = manifest["condition"] == FLAT_V2_CONDITION
        addon = root.get("lineage_flat_addon") or {}
        parent = ParentMaterial(
            0, Path(artifacts["teacher_code"]["path"]).read_text(encoding="utf-8"),
            root["standardized_verdict"], artifacts["teacher_code"]["sha256"],
            Path(artifacts["flat_ff_payload"]["path"]).read_text(encoding="utf-8"),
            artifacts["flat_ff_payload"]["sha256"], root["flat_renderer_version"],
            artifacts["flat_ff_record"]["path"] if is_flat_v2 else None,
            addon.get("validated_record_sha256") if is_flat_v2 else None,
            (Path(artifacts["lineage_flat_addon"]["path"]).read_text(
                encoding="utf-8") if is_flat_v2 else None),
            artifacts["lineage_flat_addon"]["path"] if is_flat_v2 else None,
            addon.get("flat_addon_sha256") if is_flat_v2 else None,
            addon.get("renderer_version") if is_flat_v2 else None,
        )
        root_generation = directory / "generations/generation_000_root"
        root_record = {
            "generation_index": 0, "source_root": True,
            "code_sha256": parent.code_sha256, "standardized_verdict": parent.verdict,
            "flat_ff_sha256": parent.flat_ff_sha256,
            "flat_renderer_version": parent.flat_renderer_version,
        }
        if is_flat_v2:
            root_record.update({
                "condition_policy": FLAT_V2_CONDITION,
                "validated_record_path": parent.validated_record_path,
                "validated_record_sha256": parent.validated_record_sha256,
                "flat_addon_path": parent.flat_addon_path,
                "flat_addon_sha256": parent.flat_addon_sha256,
                "flat_addon_renderer_version": parent.flat_addon_renderer_version,
            })
        write_json(root_generation / "generation.json", root_record)
        generations, ancestors = [], [parent]
        outcome = "COMPLETED_UNSOLVED"
        for generation in range(1, self.config.max_generations + 1):
            gen_dir = directory / "generations" / f"generation_{generation:03d}"
            inherited = ""
            if manifest["condition"] != INDEPENDENT_RESTART_CONDITION:
                include_flat_v1 = manifest["condition"] == FLAT_V1_CONDITION
                include_flat_v2 = manifest["condition"] == FLAT_V2_CONDITION
                template_name = (
                    "code_verdict_flat_chain_v2.md" if include_flat_v2 else
                    "code_verdict_flat_chain_v1.md" if include_flat_v1 else
                    "code_verdict_chain_v1.md")
                inherited = adapter.renderer.render(
                    adapter.renderer.template(template_name),
                    parent_code=parent.code.rstrip(), parent_verdict=parent.verdict,
                    parent_flat_ff=(parent.flat_ff or "").rstrip(),
                    parent_flat_addon=(parent.flat_addon or "").rstrip(),
                ).rstrip() + "\n"
                canonical = (
                    render_inherited_payload_v2(parent) if include_flat_v2 else
                    render_inherited_payload(parent, include_flat=include_flat_v1)
                )
                if inherited != canonical:
                    raise ValueError("lineage prompt template differs from frozen renderer")
            audit = audit_direct_parent_payload(inherited, parent, ancestors[:-1])
            audit.extend(audit_structured_parent_sources(parent))
            audit = sorted(set(audit))
            if audit:
                raise ValueError("direct-parent payload audit failed: " + ",".join(audit))
            write_text(gen_dir / "inherited_payload.txt", inherited)
            complete_payload = (
                complete_model_visible_payload(problem, inherited)
                if inherited else problem.rstrip() + "\n")
            complete_payload_path = gen_dir / "complete_model_visible_payload.txt"
            write_text(complete_payload_path, complete_payload)
            generation_manifest = {
                **{k: manifest[k] for k in ("condition", "problem_id", "root_episode_id",
                    "lineage_repeat_index")},
                "generation_index": generation, "parent_generation_index": parent.generation,
                "parent_code_sha256": parent.code_sha256 if inherited else None,
                "parent_verdict": parent.verdict if inherited else None,
                "parent_flat_ff_sha256": parent.flat_ff_sha256 if manifest["condition"] == FLAT_V1_CONDITION else None,
                "parent_flat_renderer_version": parent.flat_renderer_version if manifest["condition"] == FLAT_V1_CONDITION else None,
                "inherited_payload_sha256": sha256_text(inherited),
                "negative_inheritance_audit": {"passed": True, "issues": []},
            }
            if inherited and manifest["condition"] == FLAT_V2_CONDITION:
                generation_manifest.update({
                    "condition_policy": FLAT_V2_CONDITION,
                    "flat_addon_renderer_version": parent.flat_addon_renderer_version,
                    "validated_record_sha256": parent.validated_record_sha256,
                    "flat_addon_sha256": parent.flat_addon_sha256,
                    "complete_inherited_payload_sha256": sha256_text(complete_payload),
                    "validated_provenance_record": {
                        "path": parent.validated_record_path,
                        "sha256": parent.validated_record_sha256,
                    },
                    "lineage_flat_addon": {
                        "path": parent.flat_addon_path,
                        "sha256": parent.flat_addon_sha256,
                        "renderer_version": parent.flat_addon_renderer_version,
                    },
                    "complete_model_visible_payload": {
                        "path": str(complete_payload_path),
                        "sha256": sha256_text(complete_payload),
                    },
                })
            locked = gen_dir / "generation_manifest.json"
            if locked.is_file() and read_json(locked) != generation_manifest:
                raise ValueError("generation or parent hash drift")
            write_json(locked, generation_manifest)
            solver = adapter._solver_stage(
                gen_dir / "solver", "student", root["problem_id"], manifest["condition"],
                problem, item, spec, additional_material=inherited)
            if manifest["condition"] == FLAT_V2_CONDITION:
                planning_call = read_json(
                    gen_dir / "solver/planning/model_call.json")
                if planning_call.get("user_prompt") != complete_payload:
                    raise ValueError("Flat-v2 planning payload differs from registered payload")
                final_call = read_json(gen_dir / "solver/final/model_call.json")
                if final_call.get("user_prompt", "").count(complete_payload.rstrip()) != 1:
                    raise ValueError("Flat-v2 final payload registration mismatch")
            generation_record = self._generation_record(
                generation_manifest, solver, gen_dir / "solver")
            if inherited and solver.get("code") is not None:
                similarity = SequenceMatcher(None, parent.code, solver["code"]).ratio()
                generation_record["normalized_code_edit_ratio"] = 1.0 - similarity
                generation_record["exact_code_repeat"] = (
                    generation_record["normalized_code_sha256"] ==
                    normalized_code_hash(parent.code))
            else:
                generation_record["normalized_code_edit_ratio"] = None
                generation_record["exact_code_repeat"] = None
            generations.append(generation_record)
            write_json(gen_dir / "generation_result.json", generation_record)
            if solver["verdict"] == "JUDGE_ERROR":
                outcome = "INVALID_INFRASTRUCTURE"
                break
            if solver["verdict"] == "AC":
                outcome = "SOLVED"
                break
            if not solver["final_code_extracted"]:
                if manifest["condition"] == INDEPENDENT_RESTART_CONDITION:
                    continue
                outcome = "TERMINATED_NO_INHERITABLE_CODE"
                break
            child = ParentMaterial(
                generation, solver["code"], solver["verdict"],
                sha256_text(solver["code"]),
            )
            if manifest["condition"] in {
                    FLAT_V1_CONDITION, FLAT_V2_CONDITION} and generation < self.config.max_generations:
                try:
                    child, flat_cost = self._generate_flat(
                        adapter, gen_dir, root["problem_id"], problem, solver,
                        child, condition=manifest["condition"])
                    generation_record.update({
                        "flat_ff_sha256": child.flat_ff_sha256,
                        "flat_renderer_version": child.flat_renderer_version,
                        "flat_ff_generation_status": "completed",
                        **flat_cost,
                    })
                    if manifest["condition"] == FLAT_V2_CONDITION:
                        generation_record.update({
                            "condition_policy": FLAT_V2_CONDITION,
                            "generated_validated_record_sha256": (
                                child.validated_record_sha256),
                            "generated_flat_addon_sha256": child.flat_addon_sha256,
                            "generated_flat_addon_renderer_version": (
                                child.flat_addon_renderer_version),
                        })
                    write_json(gen_dir / "generation_result.json", generation_record)
                except ModelInfrastructureError:
                    raise
                except Exception as error:
                    workspace = gen_dir / "flat_ff"
                    record_path = workspace / (
                        "teaching_materials/provenance_ff_v2/"
                        "failure_frontier_record.json")
                    rejection_path = workspace / (
                        "teaching_materials/provenance_ff_v2/"
                        "rejected_low_confidence_excerpts.json")
                    write_json(gen_dir / "flat_ff_protocol_failure.json", {
                        "failure_stage": "generation_or_validation",
                        "error_type": type(error).__name__, "message": str(error),
                        "fallback_used": False,
                        "organizer_response_artifact": str(workspace /
                            "ff_organizer/content.md"),
                        "validated_record_artifact": (
                            str(record_path) if record_path.is_file() else None),
                        "validated_record_sha256": (
                            canonical_hash(read_json(record_path))
                            if record_path.is_file() else None),
                        "rejection_audit_artifact": (
                            str(rejection_path) if rejection_path.is_file() else None),
                        "rejection_audit_sha256": (
                            canonical_hash(read_json(rejection_path))
                            if rejection_path.is_file() else None),
                        "parent_code_sha256": child.code_sha256,
                        "parent_verdict": child.verdict,
                        "flat_addon_renderer_version": (
                            LINEAGE_FLAT_ADDON_RENDERER_VERSION
                            if manifest["condition"] == FLAT_V2_CONDITION else None),
                    })
                    generation_record["flat_ff_generation_status"] = "protocol_failure"
                    write_json(gen_dir / "generation_result.json", generation_record)
                    outcome = "TERMINATED_FLAT_FF_PROTOCOL_FAILURE"
                    break
            parent = child
            ancestors.append(child)
        return self._summarize(manifest, generations, outcome)

    def _generate_flat(self, adapter: LineagePilotAdapter, gen_dir: Path,
                       problem_id: str, problem: str, solver: dict[str, Any],
                       parent: ParentMaterial, *, condition: str,
                       ) -> tuple[ParentMaterial, dict[str, int]]:
        workspace = gen_dir / "flat_ff"
        if condition == FLAT_V2_CONDITION:
            completed = self._load_completed_flat_v2(workspace, parent)
            if completed is not None:
                return completed
        if self.flat_pipeline is not None:
            request = {"workspace": workspace, "problem_id": problem_id,
                       "problem": problem, "solver": solver, "parent": parent}
            raw_path = workspace / "offline_raw_generation.json"
            if hasattr(self.flat_pipeline, "generate"):
                if raw_path.is_file():
                    raw = read_json(raw_path)
                else:
                    raw = self.flat_pipeline.generate(**request)
                    write_json(raw_path, raw)
                result = self.flat_pipeline.validate(raw=raw, **request)
            else:
                result = self.flat_pipeline(**request)
            if condition == FLAT_V2_CONDITION:
                record = result["record"]
                record_path = workspace / (
                    "teaching_materials/provenance_ff_v2/failure_frontier_record.json")
                write_json(record_path, record)
                rejection_path = workspace / (
                    "teaching_materials/provenance_ff_v2/"
                    "rejected_low_confidence_excerpts.json")
                write_json(rejection_path, result.get("rejection_audit", {
                    "policy": "offline_fixture", "received_excerpt_count": 0,
                    "accepted_excerpt_count": len(
                        record.get("selected_low_confidence_excerpts", [])),
                    "rejected_excerpt_count": 0, "rejected_excerpts": [],
                }))
                cost = {
                    "flat_ff_model_calls": result.get("model_calls", 2),
                    "flat_ff_prompt_tokens": result.get("prompt_tokens", 20),
                    "flat_ff_completion_tokens": result.get("completion_tokens", 10),
                    "flat_ff_total_tokens": result.get("total_tokens", 30),
                }
                return self._persist_flat_v2(
                    workspace, parent, record, canonical_hash(record), cost,
                    pipeline="injected_offline_fixture",
                )
            flat = result["flat_payload"]
            write_text(workspace / "teaching_materials/provenance_ff_v2/flat_failure_payload.txt", flat)
            write_json(workspace / "flat_ff.state.json", {
                "status": "completed", "pipeline": "injected_offline_fixture",
                "flat_ff_sha256": sha256_text(flat),
                "flat_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
                "validation_passed": True,
            })
            cost = {
                "flat_ff_model_calls": result.get("model_calls", 2),
                "flat_ff_prompt_tokens": result.get("prompt_tokens", 20),
                "flat_ff_completion_tokens": result.get("completion_tokens", 10),
                "flat_ff_total_tokens": result.get("total_tokens", 30),
            }
            return ParentMaterial(
                parent.generation, parent.code, parent.verdict, parent.code_sha256,
                flat, sha256_text(flat), FLAT_PAYLOAD_RENDERER_VERSION), cost
        write_text(workspace / "teacher/planning/content.md", solver["planning_response"])
        write_text(workspace / "teacher/final/extracted_solution.py", solver["code"])
        bundle = adapter._provenance_failure_material(
            workspace, problem_id, problem, solver)
        calls = [read_json(path) for path in workspace.rglob("model_call.json")]
        responses = [call["response"] for call in calls]
        cost = {
            "flat_ff_model_calls": len(calls),
            "flat_ff_prompt_tokens": sum(r["input_tokens"] for r in responses),
            "flat_ff_completion_tokens": sum(r["output_tokens"] for r in responses),
            "flat_ff_total_tokens": sum(r["total_tokens"] for r in responses),
        }
        if condition == FLAT_V2_CONDITION:
            return self._persist_flat_v2(
                workspace, parent, bundle["record"], bundle["record_sha256"],
                cost, pipeline="PilotRunner._provenance_failure_material",
                rejected_excerpt_audit_sha256=(
                    bundle["rejected_excerpt_audit_sha256"]),
            )
        flat = bundle["flat_payload"]
        state = {
            "status": "completed", "pipeline": "PilotRunner._provenance_failure_material",
            "flat_ff_sha256": sha256_text(flat),
            "flat_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
            "organizer_record_sha256": bundle["record_sha256"],
            "rejected_excerpt_audit_sha256": bundle["rejected_excerpt_audit_sha256"],
        }
        write_json(workspace / "flat_ff.state.json", state)
        return ParentMaterial(parent.generation, parent.code, parent.verdict,
                              parent.code_sha256, flat, state["flat_ff_sha256"],
                              FLAT_PAYLOAD_RENDERER_VERSION), cost

    def _persist_flat_v2(
        self, workspace: Path, parent: ParentMaterial,
        record: dict[str, Any], record_sha256: str, cost: dict[str, int],
        *, pipeline: str,
        rejected_excerpt_audit_sha256: str | None = None,
    ) -> tuple[ParentMaterial, dict[str, int]]:
        if canonical_hash(record) != record_sha256:
            raise ValueError("validated provenance record hash mismatch")
        rendered = render_lineage_flat_analysis(record)
        material_dir = workspace / "teaching_materials/provenance_ff_v2"
        source_manifest_path = material_dir / "source_manifest.json"
        raw_sources: tuple[str, ...] = ()
        if source_manifest_path.is_file():
            source_manifest = read_json(source_manifest_path)
            raw_sources = tuple(
                Path(metadata["source_artifact"]).read_text(encoding="utf-8")
                for metadata in source_manifest.get("source_sha256", {}).values()
            )
        audit_addon_excludes_complete_sources(
            rendered, parent_code=parent.code,
            raw_source_contents=raw_sources,
        )
        record_path = material_dir / "failure_frontier_record.json"
        if not record_path.is_file():
            write_json(record_path, record)
        if canonical_hash(read_json(record_path)) != record_sha256:
            raise ValueError("persisted validated provenance record hash mismatch")
        addon_path = material_dir / "lineage_flat_addon.txt"
        addon_manifest_path = material_dir / "lineage_flat_addon.manifest.json"
        write_text(addon_path, rendered.text)
        write_json(addon_manifest_path, rendered.manifest())
        state = {
            "status": "completed",
            "condition_policy": FLAT_V2_CONDITION,
            "pipeline": pipeline,
            "validated_record_path": str(record_path),
            "validated_record_sha256": record_sha256,
            "flat_addon_path": str(addon_path),
            "flat_addon_sha256": rendered.sha256,
            "flat_addon_manifest_path": str(addon_manifest_path),
            "flat_addon_manifest_sha256": file_hash(addon_manifest_path),
            "flat_addon_renderer_version": LINEAGE_FLAT_ADDON_RENDERER_VERSION,
            "parent_code_sha256": parent.code_sha256,
            "parent_verdict": parent.verdict,
            "rejected_excerpt_audit_sha256": rejected_excerpt_audit_sha256,
            **cost,
        }
        write_json(workspace / "flat_ff.state.json", state)
        return ParentMaterial(
            parent.generation, parent.code, parent.verdict, parent.code_sha256,
            validated_record_path=str(record_path),
            validated_record_sha256=record_sha256,
            flat_addon=rendered.text, flat_addon_path=str(addon_path),
            flat_addon_sha256=rendered.sha256,
            flat_addon_renderer_version=LINEAGE_FLAT_ADDON_RENDERER_VERSION,
        ), cost

    def _load_completed_flat_v2(
        self, workspace: Path, parent: ParentMaterial,
    ) -> tuple[ParentMaterial, dict[str, int]] | None:
        state_path = workspace / "flat_ff.state.json"
        if not state_path.is_file():
            return None
        state = read_json(state_path)
        if state.get("status") != "completed":
            return None
        required = {
            "condition_policy": FLAT_V2_CONDITION,
            "flat_addon_renderer_version": LINEAGE_FLAT_ADDON_RENDERER_VERSION,
            "parent_code_sha256": parent.code_sha256,
            "parent_verdict": parent.verdict,
        }
        if any(state.get(key) != value for key, value in required.items()):
            raise ValueError("completed Flat-v2 state identity drift")
        record_path = Path(state["validated_record_path"])
        addon_path = Path(state["flat_addon_path"])
        addon_manifest_path = Path(state["flat_addon_manifest_path"])
        if canonical_hash(read_json(record_path)) != state["validated_record_sha256"]:
            raise ValueError("completed Flat-v2 validated-record hash drift")
        if file_hash(addon_path) != state["flat_addon_sha256"]:
            raise ValueError("completed Flat-v2 add-on hash drift")
        if file_hash(addon_manifest_path) != state["flat_addon_manifest_sha256"]:
            raise ValueError("completed Flat-v2 add-on manifest hash drift")
        record = read_json(record_path)
        rerendered = render_lineage_flat_analysis(record)
        addon = addon_path.read_text(encoding="utf-8")
        if addon != rerendered.text or rerendered.sha256 != state["flat_addon_sha256"]:
            raise ValueError("completed Flat-v2 deterministic rerender drift")
        cost = {key: int(state[key]) for key in (
            "flat_ff_model_calls", "flat_ff_prompt_tokens",
            "flat_ff_completion_tokens", "flat_ff_total_tokens")}
        return ParentMaterial(
            parent.generation, parent.code, parent.verdict, parent.code_sha256,
            validated_record_path=str(record_path),
            validated_record_sha256=state["validated_record_sha256"],
            flat_addon=addon, flat_addon_path=str(addon_path),
            flat_addon_sha256=state["flat_addon_sha256"],
            flat_addon_renderer_version=state["flat_addon_renderer_version"],
        ), cost

    @staticmethod
    def _generation_record(manifest: dict[str, Any], solver: dict[str, Any],
                           solver_dir: Path) -> dict[str, Any]:
        code = solver.get("code")
        calls = [read_json(path) for path in solver_dir.rglob("model_call.json")]
        responses = [call["response"] for call in calls]
        prompt_tokens = sum(r["input_tokens"] for r in responses)
        completion_tokens = sum(r["output_tokens"] for r in responses)
        total_tokens = sum(r["total_tokens"] for r in responses)
        return {
            **manifest, "standardized_verdict": solver["verdict"],
            "code_sha256": sha256_text(code) if code is not None else None,
            "normalized_code_sha256": normalized_code_hash(code) if code is not None else None,
            "final_code_extracted": solver["final_code_extracted"],
            "judge_comparable": solver["final_code_extracted"] and solver["verdict"] != "JUDGE_ERROR",
            "system_attempt_valid": solver["verdict"] != "JUDGE_ERROR",
            "integrity_valid": True,
            "infrastructure_status": "ok",
            "stage_completion": {
                "planning": True, "final": True, "extraction": True,
                "judge": bool(solver["judge_submissions"]),
            },
            "planning_calls": solver["planning_calls"], "final_calls": solver["final_calls"],
            "judge_submissions": solver["judge_submissions"],
            "planning_truncated": solver["planning_truncated"],
            "final_truncated": solver["final_truncated"],
            "student_prompt_tokens": prompt_tokens,
            "student_completion_tokens": completion_tokens,
            "student_total_tokens": total_tokens,
            "finish_reasons": [r["finish_reason"] for r in responses],
            "flat_ff_generation_status": "not_required",
            "flat_ff_model_calls": 0, "flat_ff_prompt_tokens": 0,
            "flat_ff_completion_tokens": 0, "flat_ff_total_tokens": 0,
            "model_protocol_failure": None if code is not None else solver.get("format_error"),
        }

    @staticmethod
    def _summarize(manifest: dict[str, Any], generations: list[dict[str, Any]], outcome: str):
        first = next((g["generation_index"] for g in generations
                      if g["standardized_verdict"] == "AC"), None)
        return {**manifest, "outcome": outcome, "first_ac_generation": first,
                "integrity_valid": outcome != "INVALID_INTEGRITY",
                "system_attempt_valid": outcome not in {"INVALID_INTEGRITY", "INVALID_INFRASTRUCTURE"},
                "generations_attempted": len(generations), "generations": generations,
                "solver_calls": sum(g["planning_calls"] + g["final_calls"] for g in generations),
                "flat_ff_model_calls": sum(g["flat_ff_model_calls"] for g in generations),
                "judge_submissions": sum(g["judge_submissions"] for g in generations),
                "student_tokens": sum(g["student_total_tokens"] for g in generations),
                "flat_ff_tokens": sum(g["flat_ff_total_tokens"] for g in generations)}

    @staticmethod
    def _invalid_summary(manifest, outcome, reason):
        return {**manifest, "outcome": outcome, "invalid_reason": reason,
                "integrity_valid": outcome != "INVALID_INTEGRITY",
                "system_attempt_valid": False,
                "first_ac_generation": None, "generations_attempted": 0,
                "generations": [], "solver_calls": 0, "flat_ff_model_calls": 0,
                "judge_submissions": 0, "student_tokens": 0, "flat_ff_tokens": 0}

    @staticmethod
    def _validate_lineage_links(directory: Path, summary: dict[str, Any]) -> None:
        previous = read_json(directory / "generations/generation_000_root/generation.json")
        for generation in summary.get("generations", []):
            index = generation["generation_index"]
            gen_dir = directory / "generations" / f"generation_{index:03d}"
            payload_path = gen_dir / "inherited_payload.txt"
            if (not payload_path.is_file() or
                    sha256_text(payload_path.read_text(encoding="utf-8")) !=
                    generation["inherited_payload_sha256"]):
                raise ValueError("inherited payload hash drift")
            if generation.get("code_sha256") is not None:
                code_path = gen_dir / "solver/final/extracted_solution.py"
                if (not code_path.is_file() or
                        file_hash(code_path) != generation["code_sha256"]):
                    raise ValueError("generation code hash drift")
            if generation["condition"] != INDEPENDENT_RESTART_CONDITION:
                if generation["parent_code_sha256"] != previous["code_sha256"]:
                    raise ValueError("parent code hash drift")
                if generation["condition"] == FLAT_V1_CONDITION and generation["parent_flat_ff_sha256"] != previous.get("flat_ff_sha256"):
                    raise ValueError("parent Flat FF hash drift")
                if generation["parent_verdict"] != previous["standardized_verdict"]:
                    raise ValueError("parent verdict drift")
            if generation["condition"] == FLAT_V2_CONDITION:
                if generation.get("condition_policy") != FLAT_V2_CONDITION:
                    raise ValueError("Flat-v2 condition policy drift")
                if generation.get("flat_addon_renderer_version") != (
                        LINEAGE_FLAT_ADDON_RENDERER_VERSION):
                    raise ValueError("Flat-v2 renderer-version drift")
                previous_record_hash = previous.get(
                    "generated_validated_record_sha256",
                    previous.get("validated_record_sha256"))
                previous_addon_hash = previous.get(
                    "generated_flat_addon_sha256",
                    previous.get("flat_addon_sha256"))
                if generation.get("validated_record_sha256") != previous_record_hash:
                    raise ValueError("parent validated-record hash drift")
                if generation.get("flat_addon_sha256") != previous_addon_hash:
                    raise ValueError("parent Flat add-on hash drift")
                record_meta = generation["validated_provenance_record"]
                if canonical_hash(read_json(Path(record_meta["path"]))) != record_meta["sha256"]:
                    raise ValueError("validated provenance record artifact drift")
                addon_meta = generation["lineage_flat_addon"]
                if (addon_meta.get("renderer_version") !=
                        LINEAGE_FLAT_ADDON_RENDERER_VERSION or
                        file_hash(Path(addon_meta["path"])) != addon_meta["sha256"]):
                    raise ValueError("lineage Flat add-on artifact drift")
                complete_meta = generation["complete_model_visible_payload"]
                if file_hash(Path(complete_meta["path"])) != complete_meta["sha256"]:
                    raise ValueError("complete model-visible payload hash drift")
                if complete_meta["sha256"] != generation[
                        "complete_inherited_payload_sha256"]:
                    raise ValueError("complete inherited-payload hash drift")
            if generation.get("flat_ff_sha256"):
                flat_path = (gen_dir /
                    "flat_ff/teaching_materials/provenance_ff_v2/flat_failure_payload.txt")
                if (not flat_path.is_file() or
                        file_hash(flat_path) != generation["flat_ff_sha256"]):
                    raise ValueError("generation Flat FF hash drift")
            if generation.get("generated_flat_addon_sha256"):
                addon_path = gen_dir / (
                    "flat_ff/teaching_materials/provenance_ff_v2/"
                    "lineage_flat_addon.txt")
                record_path = gen_dir / (
                    "flat_ff/teaching_materials/provenance_ff_v2/"
                    "failure_frontier_record.json")
                if (not addon_path.is_file() or
                        file_hash(addon_path) != generation[
                            "generated_flat_addon_sha256"]):
                    raise ValueError("generation Flat add-on hash drift")
                if (not record_path.is_file() or canonical_hash(
                        read_json(record_path)) != generation[
                            "generated_validated_record_sha256"]):
                    raise ValueError("generation validated-record hash drift")
            previous = generation
