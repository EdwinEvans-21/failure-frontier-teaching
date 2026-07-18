from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import shutil

from experiments.pilot.prompts import PromptRenderer
from experiments.pilot.storage import write_json, write_text
from ffjudge.models import ProblemSpec

from .schedule import PROBLEM_IDS


SOURCE_RUN_ID = "expanded-exploratory-v1-20260718T044702Z"
ELIGIBILITY_POLICY = "fixed_material_student_comparison_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_verified(source: Path, destination: Path) -> dict[str, Any]:
    source_hash = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    copied_hash = sha256_file(destination)
    if source_hash != copied_hash:
        raise RuntimeError(f"snapshot copy hash mismatch: {source.name}")
    return {
        "source_path": str(source.resolve()),
        "source_sha256": source_hash,
        "snapshot_path": str(destination.resolve()),
        "snapshot_sha256": copied_hash,
    }


def _source_rows(source_run: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in (source_run / "results.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[row["problem_id"]] = row
    return rows


def _eligible(row: dict[str, Any]) -> list[str]:
    material = row.get("teaching_material", {})
    errors: list[str] = []
    checks = {
        "branch": row.get("branch") == "teacher_failure",
        "condition_comparison_eligible": row.get("condition_comparison_eligible") is True,
        "token_match_passed": material.get("token_match_passed") is True,
        "fallback_candidate_used": material.get("fallback_candidate_used") is False,
        "failure_frontier_output_limit_reached": (
            material.get("failure_frontier_output_limit_reached") is False
        ),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    return errors


def _repository_problem_map(project_root: Path) -> dict[str, dict[str, str]]:
    config = _read_json(project_root / "experiments/configs/expanded_exploratory_v1.yaml")
    result: dict[str, dict[str, str]] = {}
    for item in config["problems"]:
        spec = ProblemSpec.load(project_root / item["problem"])
        result[spec.problem_id] = item
    return result


def build_fixed_material_snapshot(
    source_run: Path,
    snapshot_root: Path,
    project_root: Path,
) -> dict[str, Any]:
    source_run = source_run.resolve()
    snapshot_root = snapshot_root.resolve()
    project_root = project_root.resolve()
    if source_run.name != SOURCE_RUN_ID:
        raise ValueError("unexpected source run ID")
    if snapshot_root.exists():
        raise FileExistsError("fixed-material snapshot directory already exists")
    rows = _source_rows(source_run)
    if any(problem_id not in rows for problem_id in PROBLEM_IDS):
        raise RuntimeError("source results do not contain all seven authoritative problems")
    problem_map = _repository_problem_map(project_root)
    source_preflight = _read_json(source_run / "preflight_manifest.json")
    renderer = PromptRenderer(project_root / "experiments/prompts")
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_policy": ELIGIBILITY_POLICY,
        "source_run_id": SOURCE_RUN_ID,
        "source_run_directory": str(source_run),
        "problem_count": len(PROBLEM_IDS),
        "problem_ids": list(PROBLEM_IDS),
        "source_runner_commit": source_preflight["git_commit"],
        "source_runner_tag": source_preflight["runner_tag"],
        "source_baseline_id": source_preflight["baseline_id"],
        "source_baseline_manifest_sha256": source_preflight[
            "expanded_baseline_manifest_sha256"
        ],
        "source_eligibility_policy": "teacher_failure_strict_v3",
        "materials": {},
    }
    artifact_records: dict[str, Any] = {}
    snapshot_root.mkdir(parents=True)
    for problem_id in PROBLEM_IDS:
        row = rows[problem_id]
        failures = _eligible(row)
        if failures:
            raise RuntimeError(f"source episode is not strictly eligible: {problem_id}")
        item = problem_map[problem_id]
        problem_dir = source_run / "problems" / problem_id
        target = snapshot_root / "materials" / problem_id
        selected = int(row["teaching_material"]["selected_version"])
        files = {
            "problem_json": project_root / item["problem"],
            "public_tests": project_root / item["public_tests"],
            "teacher_planning": problem_dir / "teacher/planning/content.md",
            "teacher_final": problem_dir / "teacher/final/content.md",
            "teacher_code": problem_dir / "teacher/final/extracted_solution.py",
            "failure_frontier_call": problem_dir /
                "teaching_materials/failure_frontier/model_call.json",
            "general_guidance": problem_dir /
                f"teaching_materials/general_guidance/version_{selected}/content.md",
            "general_guidance_match": problem_dir /
                "teaching_materials/general_guidance/match.json",
            "source_record": problem_dir / "record.json",
        }
        missing = [name for name, path in files.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"missing source artifacts for {problem_id}: {missing}")
        copied: dict[str, Any] = {}
        for name, path in files.items():
            suffix = path.suffix or ".bin"
            copied[name] = _copy_verified(path, target / f"{name}{suffix}")
        ff_call = _read_json(files["failure_frontier_call"])
        ff_text = ff_call["response"]["content"]
        ff_path = target / "failure_frontier.md"
        write_text(ff_path, ff_text)
        ff_hash = sha256_file(ff_path)
        formatted = renderer.formatted_problem(files["problem_json"], files["public_tests"])
        formatted_path = target / "formatted_problem.md"
        write_text(formatted_path, formatted)
        formatted_hash = sha256_file(formatted_path)
        gg_hash = sha256_file(target / "general_guidance.md")
        material = row["teaching_material"]
        manifest["materials"][problem_id] = {
            "teacher_verdict": row["teacher"]["verdict"],
            "formatted_problem_sha256": formatted_hash,
            "teacher_planning_sha256": copied["teacher_planning"]["source_sha256"],
            "teacher_final_sha256": copied["teacher_final"]["source_sha256"],
            "teacher_code_sha256": copied["teacher_code"]["source_sha256"],
            "failure_frontier_sha256": ff_hash,
            "failure_frontier_tokens": material["failure_frontier_tokens"],
            "general_guidance_sha256": gg_hash,
            "general_guidance_tokens": material["general_guidance_tokens"],
            "general_guidance_lower_bound": material["lower_bound"],
            "general_guidance_upper_bound": material["upper_bound"],
            "source_condition_comparison_eligible": True,
            "source_token_match_passed": True,
            "source_fallback_candidate_used": False,
            "failure_frontier_output_limit_reached": False,
            "repository_problem_path": item["problem"],
            "repository_public_tests_path": item["public_tests"],
            "repository_hidden_tests_path": item["hidden_tests"],
            "snapshot_directory": str(target),
        }
        artifact_records[problem_id] = copied | {
            "failure_frontier_material": {
                "snapshot_path": str(ff_path), "snapshot_sha256": ff_hash,
                "derived_from": str(files["failure_frontier_call"]),
            },
            "formatted_problem": {
                "snapshot_path": str(formatted_path), "snapshot_sha256": formatted_hash,
            },
        }
    manifest_path = snapshot_root / "fixed_material_manifest.json"
    write_json(manifest_path, manifest)
    write_json(snapshot_root / "source_artifact_sha256.json", artifact_records)
    review = verify_fixed_material_snapshot(snapshot_root, project_root)
    write_json(snapshot_root / "fixed_material_manifest_review.json", review)
    if not review["passed"]:
        raise RuntimeError("fixed-material snapshot self-review failed")
    return manifest


def verify_fixed_material_snapshot(snapshot_root: Path, project_root: Path) -> dict[str, Any]:
    snapshot_root = snapshot_root.resolve()
    manifest_path = snapshot_root / "fixed_material_manifest.json"
    errors: list[str] = []
    if not manifest_path.is_file():
        return {"passed": False, "errors": ["manifest_missing"]}
    manifest = _read_json(manifest_path)
    if manifest.get("problem_ids") != list(PROBLEM_IDS):
        errors.append("problem_list_drift")
    for problem_id in PROBLEM_IDS:
        record = manifest.get("materials", {}).get(problem_id)
        if not record:
            errors.append(f"material_record_missing:{problem_id}")
            continue
        root = snapshot_root / "materials" / problem_id
        expected = {
            "formatted_problem.md": record["formatted_problem_sha256"],
            "teacher_planning.md": record["teacher_planning_sha256"],
            "teacher_final.md": record["teacher_final_sha256"],
            "teacher_code.py": record["teacher_code_sha256"],
            "failure_frontier.md": record["failure_frontier_sha256"],
            "general_guidance.md": record["general_guidance_sha256"],
        }
        for name, digest in expected.items():
            path = root / name
            if not path.is_file():
                errors.append(f"missing:{problem_id}:{name}")
            elif sha256_file(path) != digest:
                errors.append(f"modified:{problem_id}:{name}")
        if not all((
            record.get("source_condition_comparison_eligible") is True,
            record.get("source_token_match_passed") is True,
            record.get("source_fallback_candidate_used") is False,
            record.get("failure_frontier_output_limit_reached") is False,
        )):
            errors.append(f"source_eligibility_drift:{problem_id}")
        for key in ("repository_problem_path", "repository_public_tests_path",
                    "repository_hidden_tests_path"):
            if not (project_root / record[key]).is_file():
                errors.append(f"repository_file_missing:{problem_id}:{key}")
    return {
        "policy": ELIGIBILITY_POLICY,
        "passed": not errors,
        "problem_count": len(PROBLEM_IDS),
        "errors": errors,
        "manifest_sha256": sha256_file(manifest_path),
    }
