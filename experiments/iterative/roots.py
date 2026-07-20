from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from ffjudge.models import ProblemSpec
from experiments.pilot.config import load_config
from experiments.pilot.provenance_ff import FLAT_PAYLOAD_RENDERER_VERSION
from experiments.pilot.storage import read_json, write_json, write_text

from .flat_addon import (
    LINEAGE_FLAT_ADDON_RENDERER_VERSION,
    audit_addon_excludes_complete_sources, render_lineage_flat_analysis,
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def locate_episode(source_run_dir: Path, episode_id: str) -> Path:
    monolithic_record = source_run_dir / "problems" / episode_id / "record.json"
    if monolithic_record.is_file():
        return source_run_dir
    direct = source_run_dir / "episodes" / episode_id
    if direct.is_dir():
        return direct
    if source_run_dir.name == episode_id and (source_run_dir / "problems").is_dir():
        return source_run_dir
    matches = [p for p in source_run_dir.rglob(episode_id) if p.is_dir() and (p / "problems").is_dir()]
    if len(matches) != 1:
        raise ValueError(f"source episode {episode_id!r} was not uniquely located")
    return matches[0]


def freeze_root(
    project_root: Path, source_run_dir: Path, episode_id: str, output_path: Path,
    *, require_lineage_flat_addon: bool = False,
) -> dict[str, Any]:
    episode = locate_episode(source_run_dir, episode_id)
    monolithic = episode / "problems" / episode_id / "record.json"
    records = [monolithic] if monolithic.is_file() else list(
        (episode / "problems").glob("*/record.json"))
    if len(records) != 1:
        raise ValueError("a root episode must contain exactly one problem record")
    record_path = records[0]
    record = read_json(record_path)
    problem_id = record["problem_id"]
    snapshot_path = episode / "config.snapshot.yaml"
    snapshot = read_json(snapshot_path)
    match = None
    for item in snapshot["problems"]:
        candidate = project_root / item["problem"]
        if ProblemSpec.load(candidate).problem_id == problem_id:
            match = item
            break
    if match is None:
        raise ValueError("problem is absent from the frozen episode config")
    problem_dir = record_path.parent
    provenance_dir = problem_dir / "teaching_materials" / "provenance_ff_v2"
    flat_path = provenance_dir / "flat_failure_payload.txt"
    ff_record_path = provenance_dir / "failure_frontier_record.json"
    source_manifest_path = provenance_dir / "source_manifest.json"
    source_manifest = read_json(source_manifest_path)
    formal_manifest_path = episode / "formal_run_manifest.json"
    integrity_report_path = episode / "integrity_report.json"
    if formal_manifest_path.is_file():
        formal_manifest = read_json(formal_manifest_path)
        if formal_manifest.get("exit_code") != 0 or not formal_manifest.get("finished_at"):
            raise ValueError("source formal run is not completed successfully")
    if integrity_report_path.is_file():
        integrity_report = read_json(integrity_report_path)
        if (integrity_report.get("git_diff_check_passed") is not True or
                integrity_report.get("baseline_v3_verification") != "passed" or
                integrity_report.get("expanded_baseline_verification") != "passed"):
            raise ValueError("source formal run integrity report is not valid")
    teacher = record.get("teacher", {})
    teacher_final = problem_dir / "teacher" / "final" / "content.md"
    teacher_code = problem_dir / "teacher" / "final" / "extracted_solution.py"
    teacher_planning = problem_dir / "teacher" / "planning" / "content.md"
    judge = problem_dir / "teacher" / "judge.internal.json"
    problem_path = (project_root / match["problem"]).resolve()
    public_path = (project_root / match["public_tests"]).resolve()
    required = [problem_path, public_path, teacher_final, teacher_code, teacher_planning,
                judge, flat_path, ff_record_path, source_manifest_path, snapshot_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError("root artifacts missing: " + ", ".join(missing))
    flat_hash = file_hash(flat_path)
    if source_manifest.get("flat_payload_sha256") != flat_hash:
        raise ValueError("root Flat FF differs from provenance source manifest")
    ff_record = read_json(ff_record_path)
    record_hash = canonical_hash(ff_record)
    if source_manifest.get("failure_frontier_record_sha256") != record_hash:
        raise ValueError("root organizer record differs from provenance source manifest")
    for metadata in source_manifest.get("source_sha256", {}).values():
        source_path = Path(metadata.get("source_artifact", ""))
        source_hash = hashlib.sha256(
            source_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest() if source_path.is_file() else None
        if source_hash != metadata.get("source_sha256"):
            raise ValueError("root provenance raw source differs from source manifest")
    provenance = record.get("provenance_failure_frontier", {})
    flat_renderer_version = source_manifest.get(
        "flat_payload_renderer_version",
        provenance.get("flat_payload_renderer_version"),
    )
    eligible = (
        teacher.get("verdict") not in {None, "AC", "JUDGE_ERROR"}
        and teacher.get("final_code_extracted") is True
        and flat_renderer_version == FLAT_PAYLOAD_RENDERER_VERSION
    )
    artifacts = {
        "public_problem": problem_path,
        "public_examples": public_path,
        "teacher_planning": teacher_planning,
        "teacher_final_raw": teacher_final,
        "teacher_code": teacher_code,
        "judge_result": judge,
        "flat_ff_payload": flat_path,
        "flat_ff_record": ff_record_path,
        "flat_ff_source_manifest": source_manifest_path,
        "source_config_snapshot": snapshot_path,
        "source_record": record_path,
    }
    lineage_addon = None
    if require_lineage_flat_addon:
        rejection_path = Path(source_manifest.get(
            "rejected_excerpt_audit_artifact", ""))
        if not rejection_path.is_file():
            raise ValueError("root rejection audit artifact is missing")
        rejection_audit = read_json(rejection_path)
        if source_manifest.get("rejected_excerpt_audit_sha256") != canonical_hash(
                rejection_audit):
            raise ValueError("root rejection audit differs from source manifest")
        artifacts["rejected_excerpt_audit"] = rejection_path
        rendered = render_lineage_flat_analysis(ff_record)
        raw_sources = tuple(
            Path(metadata["source_artifact"]).read_text(encoding="utf-8")
            for metadata in source_manifest.get("source_sha256", {}).values()
        )
        audit_addon_excludes_complete_sources(
            rendered,
            parent_code=teacher_code.read_text(encoding="utf-8"),
            raw_source_contents=raw_sources,
        )
        addon_dir = output_path.parent / f"{episode_id}.artifacts"
        addon_path = addon_dir / "lineage_flat_addon.txt"
        addon_manifest_path = addon_dir / "lineage_flat_addon.manifest.json"
        write_text(addon_path, rendered.text)
        write_json(addon_manifest_path, rendered.manifest())
        artifacts["lineage_flat_addon"] = addon_path
        artifacts["lineage_flat_addon_manifest"] = addon_manifest_path
        lineage_addon = {
            "condition_policy": "code_verdict_flat_ff_chain_v2",
            "renderer_version": LINEAGE_FLAT_ADDON_RENDERER_VERSION,
            "validated_record_sha256": record_hash,
            "flat_addon_sha256": rendered.sha256,
        }
    if formal_manifest_path.is_file():
        artifacts["source_formal_run_manifest"] = formal_manifest_path
    if integrity_report_path.is_file():
        artifacts["source_integrity_report"] = integrity_report_path
    root = {
        "schema_version": "1.0",
        "experiment_policy": "minimal_failure_lineage_v1",
        "source_run_id": record.get("run_id", episode.name),
        "source_episode_id": episode_id,
        "problem_id": problem_id,
        "standardized_verdict": teacher["verdict"],
        "source_episode_valid": record.get("valid_episode"),
        "teacher_root_eligibility_policy": "teacher_stage_and_provenance_v2",
        "flat_renderer_version": FLAT_PAYLOAD_RENDERER_VERSION,
        "lineage_flat_addon": lineage_addon,
        "root_eligibility": eligible,
        "root_eligibility_reasons": [] if eligible else ["source_episode_not_eligible"],
        "model": snapshot.get("model", {}),
        "prompt_policy": {
            "failure_frontier_policy": snapshot.get("failure_frontier_policy"),
            "teacher_failure_analysis_policy": snapshot.get("teacher_failure_analysis_policy"),
            "flat_ff_policy": snapshot.get("flat_ff_policy"),
        },
        "artifacts": {
            name: {"path": str(path), "sha256": file_hash(path)}
            for name, path in artifacts.items()
        },
    }
    root["root_manifest_sha256"] = canonical_hash(root)
    write_json(output_path, root)
    if not eligible:
        raise ValueError("root episode failed eligibility checks")
    return root


def validate_root(root: dict[str, Any]) -> None:
    expected = root.get("root_manifest_sha256")
    unsigned = dict(root)
    unsigned.pop("root_manifest_sha256", None)
    if canonical_hash(unsigned) != expected:
        raise ValueError("source root manifest hash drift")
    if root.get("root_eligibility") is not True:
        raise ValueError("source root is not eligible")
    for metadata in root.get("artifacts", {}).values():
        path = Path(metadata["path"])
        if not path.is_file() or file_hash(path) != metadata["sha256"]:
            raise ValueError("source root artifact hash drift")
    addon = root.get("lineage_flat_addon")
    if addon is not None:
        if addon.get("condition_policy") != "code_verdict_flat_ff_chain_v2":
            raise ValueError("root Flat add-on condition policy drift")
        if addon.get("renderer_version") != LINEAGE_FLAT_ADDON_RENDERER_VERSION:
            raise ValueError("root Flat add-on renderer-version drift")
        record = root["artifacts"]["flat_ff_record"]
        if addon.get("validated_record_sha256") != canonical_hash(read_json(Path(record["path"]))):
            raise ValueError("root validated-record hash drift")
        flat = root["artifacts"]["lineage_flat_addon"]
        if addon.get("flat_addon_sha256") != file_hash(Path(flat["path"])):
            raise ValueError("root Flat add-on hash drift")
        rerendered = render_lineage_flat_analysis(read_json(Path(record["path"])))
        if (rerendered.text != Path(flat["path"]).read_text(encoding="utf-8") or
                rerendered.sha256 != addon.get("flat_addon_sha256")):
            raise ValueError("root Flat add-on deterministic rerender drift")


def find_problem_config(base_config_path: Path, problem_id: str, project_root: Path):
    config = load_config(base_config_path)
    for item in config.problems:
        if ProblemSpec.load(project_root / item.problem).problem_id == problem_id:
            return config, item
    raise ValueError(f"problem {problem_id} is absent from base config")
