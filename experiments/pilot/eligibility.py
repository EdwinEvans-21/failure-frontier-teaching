from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ELIGIBILITY_POLICY = "teacher_failure_selected_gg_v4"
V2_ELIGIBILITY_POLICY = "teacher_failure_semantic_gg_no_length_v5"
ELIGIBILITY_REASON_PRECEDENCE = (
    "infrastructure_error",
    "invalid_episode",
    "teacher_success_branch",
    "failure_frontier_output_limit_reached",
    "gg_candidate_missing_or_unsafe",
    "gg_token_outside_interval",
    "gg_candidate_truncated",
    "students_incomplete",
    "student_material_invalid",
)
REQUIRED_STUDENTS = (
    "success_only",
    "failure_frontier",
    "general_guidance",
)
REQUIRED_V2_STUDENTS = (
    "baseline", "direct_ff_v2", "critical_ff_v2", "flat_ff_v2",
    "general_guidance",
)
COMPLETED_SOLVER_VERDICTS = {"AC", "WA", "CE", "RE", "TLE", "MLE"}


@dataclass(frozen=True)
class EligibilityResult:
    branch: str | None
    condition_comparison_eligible: bool
    exploratory_comparison_eligible: bool
    eligibility_reason: str
    eligibility_reasons: tuple[str, ...]
    eligibility_policy: str = ELIGIBILITY_POLICY

    def record_fields(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "condition_comparison_eligible": (
                self.condition_comparison_eligible
            ),
            "exploratory_comparison_eligible": (
                self.exploratory_comparison_eligible
            ),
            "eligibility_reason": self.eligibility_reason,
            "eligibility_reasons": list(self.eligibility_reasons),
            "eligibility_policy": self.eligibility_policy,
        }


def episode_branch(record: dict[str, Any]) -> str | None:
    """Return the explicit branch, or infer it for a legacy record."""
    branch = record.get("branch")
    if branch in {"teacher_success", "teacher_failure"}:
        return branch
    verdict = record.get("teacher", {}).get("verdict")
    if verdict == "AC":
        return "teacher_success"
    if verdict:
        return "teacher_failure"
    return None


def _students_completed(record: dict[str, Any]) -> bool:
    students = record.get("students")
    if not isinstance(students, dict):
        return False
    required = (
        REQUIRED_V2_STUDENTS
        if record.get("provenance_failure_frontier", {}).get(
            "failure_frontier_policy_version") ==
            "provenance_stratified_ff_v2"
        else REQUIRED_STUDENTS
    )
    for condition in required:
        student = students.get(condition)
        if not isinstance(student, dict):
            return False
        if student.get("planning_calls") != 1:
            return False
        if student.get("final_calls") != 1:
            return False
        if student.get("verdict") not in COMPLETED_SOLVER_VERDICTS:
            return False
    return True


def _gg_selected_and_safe(material: dict[str, Any]) -> bool:
    return (
        isinstance(material.get("selected_version"), int)
        and isinstance(material.get("general_guidance_tokens"), int)
        and material.get("general_guidance_tokens") >= 0
        and not material.get("forbidden_content")
    )


def _gg_complete_response(material: dict[str, Any]) -> bool:
    return (
        material.get("general_guidance_truncated") is not True
        and material.get("obviously_truncated") is not True
    )


def _student_materials_valid(material: dict[str, Any]) -> bool:
    failure_frontier_tokens = material.get("failure_frontier_tokens")
    return (
        material.get("type") == "failure"
        and isinstance(failure_frontier_tokens, int)
        and failure_frontier_tokens > 0
        and material.get("failure_frontier_truncated") is not True
        and material.get("failure_frontier_output_limit_reached") is not True
    )


def derive_comparison_eligibility(
    record: dict[str, Any],
) -> EligibilityResult:
    """Deterministically derive strict and exploratory comparison eligibility.

    This function reads only finalized episode state. It performs no I/O and
    does not mutate ``record``.
    """
    branch = episode_branch(record)
    v2 = record.get("provenance_failure_frontier", {}).get(
        "failure_frontier_policy_version") == "provenance_stratified_ff_v2"
    reasons: list[str] = []

    if record.get("infrastructure_error"):
        reasons.append("infrastructure_error")
    if record.get("valid_episode") is not True:
        reasons.append("invalid_episode")

    if branch == "teacher_success":
        reasons.append("teacher_success_branch")
    elif branch != "teacher_failure":
        if "invalid_episode" not in reasons:
            reasons.append("invalid_episode")
    else:
        material = record.get("teaching_material")
        if not isinstance(material, dict):
            material = {}
        students_completed = _students_completed(record)
        selected_and_safe = _gg_selected_and_safe(material)
        selected_in_interval = (
            material.get("selected_within_token_interval") is True
        )
        selected_semantically_valid = (
            material.get("selected_format_valid") is True
            and material.get("semantic_completeness_passed") is True
        )
        complete_response = _gg_complete_response(material)

        if material.get("failure_frontier_output_limit_reached") is True:
            reasons.append("failure_frontier_output_limit_reached")
        if (not selected_and_safe or record.get("protocol_output_invalid") is True
                or (v2 and not selected_semantically_valid)):
            reasons.append("gg_candidate_missing_or_unsafe")
        elif not v2 and not selected_in_interval:
            reasons.append("gg_token_outside_interval")
        if selected_and_safe and not complete_response:
            reasons.append("gg_candidate_truncated")
        if not students_completed:
            reasons.append("students_incomplete")
        if not _student_materials_valid(material):
            reasons.append("student_material_invalid")

    ordered_reasons = tuple(
        reason for reason in ELIGIBILITY_REASON_PRECEDENCE
        if reason in reasons
    )
    strict = not ordered_reasons

    material = record.get("teaching_material")
    if not isinstance(material, dict):
        material = {}
    exploratory = (
        branch == "teacher_failure"
        and record.get("valid_episode") is True
        and not record.get("infrastructure_error")
        and record.get("protocol_output_invalid") is not True
        and material.get("failure_frontier_output_limit_reached") is not True
        and _gg_selected_and_safe(material)
        and _students_completed(record)
        and _student_materials_valid(material)
        and not strict
    )

    return EligibilityResult(
        branch=branch,
        condition_comparison_eligible=strict,
        exploratory_comparison_eligible=exploratory,
        eligibility_reason=ordered_reasons[0] if ordered_reasons else "eligible",
        eligibility_reasons=ordered_reasons or ("eligible",),
        eligibility_policy=(V2_ELIGIBILITY_POLICY if v2 else ELIGIBILITY_POLICY),
    )


def finalize_comparison_eligibility(record: dict[str, Any]) -> EligibilityResult:
    """Apply the canonical derivation immediately before record persistence."""
    result = derive_comparison_eligibility(record)
    record.update(result.record_fields())
    return result


def analyze_historical_eligibility(record: dict[str, Any]) -> dict[str, Any]:
    """Analyze a legacy artifact without modifying or overwriting it."""
    reported = record.get("condition_comparison_eligible")
    result = derive_comparison_eligibility(record)
    warnings: list[str] = []
    if record.get("branch") not in {"teacher_success", "teacher_failure"}:
        warnings.append("legacy_branch_inferred")
    if reported is not None and reported != result.condition_comparison_eligible:
        warnings.append("legacy_condition_comparison_eligibility_drift")
    return {
        "runner_reported_condition_comparison_eligible": reported,
        "protocol_condition_comparison_eligible": (
            result.condition_comparison_eligible
        ),
        "protocol_exploratory_comparison_eligible": (
            result.exploratory_comparison_eligible
        ),
        "branch": result.branch,
        "eligibility_reason": result.eligibility_reason,
        "eligibility_reasons": list(result.eligibility_reasons),
        "eligibility_policy": result.eligibility_policy,
        "compatibility_warnings": warnings,
    }
