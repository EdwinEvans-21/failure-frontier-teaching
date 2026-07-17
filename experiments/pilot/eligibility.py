from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ELIGIBILITY_POLICY = "teacher_failure_strict_v2"
ELIGIBILITY_REASON_PRECEDENCE = (
    "infrastructure_error",
    "invalid_episode",
    "teacher_success_branch",
    "token_match_failed",
    "fallback_candidate_used",
    "gg_candidate_invalid",
    "students_incomplete",
    "student_material_invalid",
)
REQUIRED_STUDENTS = (
    "success_only",
    "failure_frontier",
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
    for condition in REQUIRED_STUDENTS:
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


def _gg_semantically_valid(material: dict[str, Any]) -> bool:
    return (
        material.get("semantic_completeness_passed") is True
        and material.get("general_guidance_truncated") is not True
        and material.get("obviously_truncated") is not True
        and not material.get("forbidden_content")
    )


def _student_materials_valid(material: dict[str, Any]) -> bool:
    failure_frontier_tokens = material.get("failure_frontier_tokens")
    return (
        material.get("type") == "failure"
        and isinstance(failure_frontier_tokens, int)
        and failure_frontier_tokens > 0
        and material.get("failure_frontier_truncated") is not True
    )


def derive_comparison_eligibility(
    record: dict[str, Any],
) -> EligibilityResult:
    """Deterministically derive strict and exploratory comparison eligibility.

    This function reads only finalized episode state. It performs no I/O and
    does not mutate ``record``.
    """
    branch = episode_branch(record)
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
        token_match_passed = (
            material.get("token_match_passed") is True
            and record.get("token_match_failed") is not True
        )
        fallback_used = material.get("fallback_used") is True
        students_completed = _students_completed(record)

        if not token_match_passed:
            reasons.append("token_match_failed")
        if fallback_used:
            reasons.append("fallback_candidate_used")
        if not _gg_semantically_valid(material):
            reasons.append("gg_candidate_invalid")
        elif token_match_passed and (
            material.get("selected_within_token_interval") is not True
            or material.get("token_interval_outcome")
            != "matched_within_tolerance"
        ):
            reasons.append("gg_candidate_invalid")
        elif record.get("protocol_output_invalid") is True:
            reasons.append("gg_candidate_invalid")
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
        and material.get("fallback_used") is True
        and _gg_semantically_valid(material)
        and _students_completed(record)
        and _student_materials_valid(material)
    )

    return EligibilityResult(
        branch=branch,
        condition_comparison_eligible=strict,
        exploratory_comparison_eligible=exploratory,
        eligibility_reason=ordered_reasons[0] if ordered_reasons else "eligible",
        eligibility_reasons=ordered_reasons or ("eligible",),
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
