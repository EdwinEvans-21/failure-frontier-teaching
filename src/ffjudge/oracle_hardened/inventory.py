from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import re


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def discover_submissions(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_root = source_root.resolve()
    fresh = json.loads((source_root / "fresh_experiment_manifest.json").read_text(encoding="utf-8"))
    run_manifest_path = source_root / "lineage_stage" / "teacher-failure-lineages" / "run_manifest.json"
    lineage_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    teacher_records = sorted((source_root / "fresh_teacher_source" / "episodes").glob("*/problems/*/teacher/submission.json"))
    for record_path in teacher_records:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        result = record.get("result", {})
        code_path = record_path.parent / "final" / "extracted_solution.py"
        if not code_path.is_file() or int(result.get("judge_submissions", 0)) != 1:
            continue
        episode_id = record_path.parents[3].name
        problem_id = record_path.parents[1].name
        rows.append(_row(source_root, code_path, record_path, problem_id, "teacher", "teacher", episode_id, 0, result.get("verdict"), result))
    gen_root = source_root / "lineage_stage" / "teacher-failure-lineages" / "lineages"
    generation_records = sorted(gen_root.glob("*/generations/generation_*/generation_result.json"))
    for result_path in generation_records:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        code_path = result_path.parent / "solver" / "final" / "extracted_solution.py"
        if not code_path.is_file() or int(result.get("judge_submissions", 0)) != 1:
            continue
        rows.append(_row(
            source_root, code_path, result_path, result["problem_id"], "student",
            result["condition"], result["root_episode_id"], int(result["generation_index"]),
            result.get("standardized_verdict"), result,
            lineage_repeat_index=int(result.get("lineage_repeat_index", 0)),
        ))
    for index, row in enumerate(rows):
        row["submission_instance_id"] = f"submission-{index:04d}"
    teacher = sum(r["role"] == "teacher" for r in rows)
    student = sum(r["role"] == "student" for r in rows)
    expected_teacher = int(fresh["teacher_samples"])
    lineages_json = source_root / "lineage_stage" / "teacher-failure-lineages" / "lineages.json"
    lineages = json.loads(lineages_json.read_text(encoding="utf-8"))
    lineage_rows = lineages if isinstance(lineages, list) else lineages.get("lineages", [])
    expected_student = sum(len(item.get("generations", [])) for item in lineage_rows)
    teacher_marked_judged = sum(int(json.loads(p.read_text(encoding="utf-8")).get("result", {}).get("judge_submissions", 0)) == 1 for p in teacher_records)
    student_marked_judged = sum(int(json.loads(p.read_text(encoding="utf-8")).get("judge_submissions", 0)) == 1 for p in generation_records)
    reconciliation = {
        "source_run_id": fresh["run_id"], "discovered_teacher": teacher,
        "manifest_teacher_samples": expected_teacher, "teacher_sample_records": len(teacher_records),
        "teacher_records_marked_judged": teacher_marked_judged,
        "discovered_student": student, "manifest_student_generations": expected_student,
        "student_generation_records": len(generation_records), "student_records_marked_judged": student_marked_judged,
        "orphan_generation_records_not_in_aggregate_manifest": len(generation_records) - expected_student,
        "discovered_total": len(rows),
        "conditions": lineage_manifest["conditions"],
        "passed": len(teacher_records) == expected_teacher and len(generation_records) >= expected_student and teacher == teacher_marked_judged and student == student_marked_judged,
    }
    return rows, reconciliation


def _row(source_root: Path, code_path: Path, record_path: Path, problem_id: str, role: str, condition: str, root_id: str, generation: int, verdict: Any, source: dict[str, Any], *, lineage_repeat_index: int = 0) -> dict[str, Any]:
    code_hash = sha256_file(code_path)
    return {
        "source_run_id": json.loads((source_root / "fresh_experiment_manifest.json").read_text(encoding="utf-8"))["run_id"],
        "problem_id": problem_id, "role": role, "condition": condition,
        "root_id": root_id, "lineage_repeat_index": lineage_repeat_index,
        "generation": generation,
        "submission_path": code_path.relative_to(source_root).as_posix(),
        "submission_sha256": code_hash,
        "source_record_path": record_path.relative_to(source_root).as_posix(),
        "source_record_sha256": sha256_file(record_path),
        "original_judge_verdict": _normalize(verdict),
        "prompt_tokens": int(source.get("student_prompt_tokens", source.get("input_tokens", 0)) or 0),
        "completion_tokens": int(source.get("student_completion_tokens", source.get("output_tokens", 0)) or 0),
        "total_tokens": int(source.get("student_total_tokens", 0) or 0),
    }


def _normalize(verdict: Any) -> str | None:
    if verdict is None:
        return None
    aliases = {"ACCEPTED": "AC", "WRONG_ANSWER": "WA", "RUNTIME_ERROR": "RE", "SYNTAX_ERROR": "CE", "TIME_LIMIT_EXCEEDED": "TLE", "MEMORY_LIMIT_EXCEEDED": "MLE"}
    return aliases.get(str(verdict), str(verdict))
