from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal
import hashlib
import json
import re


FAILURE_FRONTIER_POLICY = "provenance_stratified_ff_v2"
TEACHER_FAILURE_ANALYSIS_POLICY = "provenance_preserved_failure_analysis_v2"
DIRECT_FF_POLICY = "direct_ff_v2"
CRITICAL_FF_POLICY = "critical_ff_v2"
RIGOROUS_REVIEW_FF_POLICY = "rigorous_review_ff_v3"
FLAT_FF_POLICY = "flat_ff_v2"
BASELINE_POLICY = "baseline_v2"
SHARED_PAYLOAD_BUILDER_VERSION = "provenance_payload_builder_v2"
FLAT_PAYLOAD_RENDERER_VERSION = "flat_provenance_payload_renderer_v2"
POLICY_REGISTRY = {
    "provenance_stratified_ff_v2": {
        "teacher_failure_analysis": "teacher_failure_analysis_v2.md",
        "organizer": "ff_organizer_v2.md",
        "payload_builder": SHARED_PAYLOAD_BUILDER_VERSION,
    },
    "direct_ff_v2": {"instruction": "direct_ff_v2.md", "legacy_alias": None},
    "critical_ff_v2": {
        "instruction": "critical_ff_v2.md", "legacy_alias": None},
    "rigorous_review_ff_v3": {
        "instruction": "rigorous_review_ff_v3.md", "legacy_alias": None},
    "flat_ff_v2": {
        "instruction": "direct_ff_v2.md", "legacy_alias": None,
        "payload_renderer": FLAT_PAYLOAD_RENDERER_VERSION,
    },
    "baseline_v2": {"instruction": "baseline_v2.md", "legacy_alias": None},
    "legacy_naive_ff_v1": {
        "condition": "failure_frontier", "historical_name": "naive_ff",
        "automatic_upgrade": False,
    },
    "critical_ff_v1": {
        "condition": "critical_failure_frontier", "automatic_upgrade": False,
    },
}

DIRECT_CONDITION = "direct_ff_v2"
CRITICAL_CONDITION = "critical_ff_v2"
RIGOROUS_REVIEW_CONDITION = "rigorous_review_ff_v3"
FLAT_CONDITION = "flat_ff_v2"
BASELINE_CONDITION = "baseline"

FINAL_ERROR_TYPES = frozenset({
    "WRONG_ANSWER",
    "TIME_LIMIT_EXCEEDED",
    "RUNTIME_ERROR",
    "MEMORY_LIMIT_EXCEEDED",
    "SYNTAX_ERROR",
    "INVALID_SUBMISSION",
})
SUPPORT_STATUSES = frozenset({
    "PROVISIONALLY_SUPPORTED", "PARTIALLY_SUPPORTED"
})
LOW_CONFIDENCE_SOURCE_TYPES = frozenset({
    "TEACHER_PLANNING",
    "TEACHER_FINAL_NATURAL_LANGUAGE",
    "TEACHER_FAILURE_ANALYSIS",
    "FF_ORGANIZER_HYPOTHESIS",
})
DIRECT_FACT_KINDS = frozenset({
    "FINAL_ERROR_TYPE", "TEACHER_SUBMITTED_CODE", "CODE_SHA256",
    "EXACT_CODE_EXCERPT", "RAW_DETERMINISTIC_FIELD",
})
FORBIDDEN_DETAILED_EVALUATION = (
    "public_tests_all_passed", "internal_result", "runtime_ms",
    "failed_case_index", "passed_test_count", "total_test_count",
    "expected_output", "actual_output", "compiler_stderr",
    "runtime_traceback", "judge_internal",
)
DIRECT_AUDIT_PHRASES = (
    "think critically about the teacher materials",
    "do not blindly trust the report",
    "verify every claim",
    "reclassify the evidence",
    "independently reconstruct the solution before using the materials",
)
FORBIDDEN_RECORD_GUIDANCE = (
    "```python", "pseudocode", "next algorithm", "next direction",
    "future search", "recommended fix", "recommend an algorithm",
    "should use the following algorithm", "replacement solution",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


@dataclass(frozen=True)
class SourceArtifact:
    source_type: str
    source_artifact: str
    source_sha256: str
    content: str

    @classmethod
    def create(cls, source_type: str, source_artifact: str,
               content: str) -> "SourceArtifact":
        if source_type not in LOW_CONFIDENCE_SOURCE_TYPES:
            raise ValueError("unsupported low-confidence source type")
        return cls(source_type, source_artifact, sha256_text(content), content)


@dataclass(frozen=True)
class DirectFact:
    kind: str
    raw_value: str
    source_artifact: str

    def __post_init__(self) -> None:
        if self.kind not in DIRECT_FACT_KINDS:
            raise ValueError("unsupported direct-fact kind")
        if not isinstance(self.raw_value, str) or not self.raw_value:
            raise ValueError("direct fact must contain a non-empty raw value")
        if self.kind == "FINAL_ERROR_TYPE" and self.raw_value not in FINAL_ERROR_TYPES:
            raise ValueError("unapproved final error type")
        if self.kind == "CODE_SHA256" and not re.fullmatch(
                r"[0-9a-f]{64}", self.raw_value):
            raise ValueError("invalid SHA-256 direct fact")
        if self.kind == "RAW_DETERMINISTIC_FIELD":
            raise ValueError("generic deterministic fields require an explicit registry")


@dataclass(frozen=True)
class EvidenceGroundedInference:
    claim: str
    evidence: str
    evidence_sources: tuple[str, ...]
    support_status: str
    reproducibility_note: str
    organizer_source: str = "FF_ORGANIZER"

    def __post_init__(self) -> None:
        if self.support_status not in SUPPORT_STATUSES:
            raise ValueError("invalid evidence support status")
        if self.organizer_source != "FF_ORGANIZER":
            raise ValueError("inference organizer source must be FF_ORGANIZER")
        allowed = {"PUBLIC_PROBLEM", "PUBLIC_CONSTRAINTS",
                   "TEACHER_SUBMITTED_CODE", "FINAL_ERROR_TYPE"}
        if not self.evidence_sources or not set(self.evidence_sources) <= allowed:
            raise ValueError("invalid inference evidence source")
        if not all((self.claim.strip(), self.evidence.strip(),
                    self.reproducibility_note.strip())):
            raise ValueError("inference fields must be non-empty")


@dataclass(frozen=True)
class SelectedLowConfidenceExcerpt:
    source_type: str
    source_artifact: str
    source_sha256: str
    exact_source_excerpt: str
    confidence_note: str

    def validate_against(self, source: SourceArtifact) -> None:
        if self.source_type != source.source_type:
            raise ValueError("low-confidence source type mismatch")
        if self.source_artifact != source.source_artifact:
            raise ValueError("low-confidence source artifact mismatch")
        if self.source_sha256 != source.source_sha256:
            raise ValueError("low-confidence source hash mismatch")
        if self.exact_source_excerpt not in source.content:
            raise ValueError("low-confidence excerpt is not verbatim")


@dataclass(frozen=True)
class OrganizerHypothesis:
    hypothesis: str
    evidence_limitation: str
    source_type: str = "FF_ORGANIZER_HYPOTHESIS"

    def __post_init__(self) -> None:
        if self.source_type != "FF_ORGANIZER_HYPOTHESIS":
            raise ValueError("organizer hypotheses require explicit provenance")


@dataclass(frozen=True)
class StudentTreatmentRequest:
    shared_solver_prompt: str
    condition_specific_instruction: str
    shared_failure_payload: str
    shared_output_requirements: str

    def render_user_prompt(self) -> str:
        return render_student_input(
            self.shared_solver_prompt,
            self.condition_specific_instruction,
            self.shared_failure_payload,
        )


@dataclass(frozen=True)
class FailureFrontierRecord:
    policy_version: str
    final_error_type: str
    code_artifact: str
    code_sha256: str
    planning_artifact: str
    failure_analysis_artifact: str
    evidence_grounded_inferences: tuple[EvidenceGroundedInference, ...]
    selected_low_confidence_excerpts: tuple[SelectedLowConfidenceExcerpt, ...]
    organizer_hypotheses: tuple[OrganizerHypothesis, ...]

    def __post_init__(self) -> None:
        if self.policy_version != FAILURE_FRONTIER_POLICY:
            raise ValueError("FF record policy mismatch")
        DirectFact("FINAL_ERROR_TYPE", self.final_error_type, "submission")
        DirectFact("CODE_SHA256", self.code_sha256, self.code_artifact)
        if len(self.evidence_grounded_inferences) > 6:
            raise ValueError("at most six evidence-grounded inferences")
        if len(self.selected_low_confidence_excerpts) > 8:
            raise ValueError("at most eight selected low-confidence excerpts")
        if len(self.organizer_hypotheses) > 3:
            raise ValueError("at most three organizer hypotheses")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureFrontierRecord":
        return cls(
            policy_version=data["policy_version"],
            final_error_type=data["final_error_type"],
            code_artifact=data["code_artifact"],
            code_sha256=data["code_sha256"],
            planning_artifact=data["planning_artifact"],
            failure_analysis_artifact=data["failure_analysis_artifact"],
            evidence_grounded_inferences=tuple(
                EvidenceGroundedInference(**item)
                for item in data.get("evidence_grounded_inferences", [])
            ),
            selected_low_confidence_excerpts=tuple(
                SelectedLowConfidenceExcerpt(**item)
                for item in data.get("selected_low_confidence_excerpts", [])
            ),
            organizer_hypotheses=tuple(
                OrganizerHypothesis(**item)
                for item in data.get("organizer_hypotheses", [])
            ),
        )


@dataclass(frozen=True)
class RejectedLowConfidenceExcerpt:
    received_index: int
    reason_code: str
    reason: str
    source_type: str
    source_artifact: str
    source_sha256: str
    exact_source_excerpt: str
    confidence_note: str


@dataclass(frozen=True)
class OrganizerParseResult:
    record: FailureFrontierRecord
    received_excerpt_count: int
    rejected_excerpts: tuple[RejectedLowConfidenceExcerpt, ...]

    @property
    def accepted_excerpt_count(self) -> int:
        return len(self.record.selected_low_confidence_excerpts)

    def rejection_audit(self) -> dict[str, Any]:
        return {
            "policy": "reject_nonverbatim_excerpt_continue_v1",
            "received_excerpt_count": self.received_excerpt_count,
            "accepted_excerpt_count": self.accepted_excerpt_count,
            "rejected_excerpt_count": len(self.rejected_excerpts),
            "rejected_excerpts": [asdict(item) for item in self.rejected_excerpts],
        }


def classify_information(*, source: str, raw_objective: bool = False,
                         short_visible_evidence_chain: bool = False) -> str:
    if raw_objective and source == "SYSTEM_RECORD":
        return "DIRECT_FACT"
    if source == "FF_ORGANIZER" and short_visible_evidence_chain:
        return "EVIDENCE_GROUNDED_INFERENCE"
    return "LOW_CONFIDENCE_HYPOTHESIS"


def standardized_error_type(teacher: dict[str, Any]) -> str | None:
    verdict = teacher.get("verdict")
    mapping = {
        "WA": "WRONG_ANSWER", "TLE": "TIME_LIMIT_EXCEEDED",
        "RE": "RUNTIME_ERROR", "MLE": "MEMORY_LIMIT_EXCEEDED",
    }
    if verdict in mapping:
        return mapping[verdict]
    if verdict == "CE":
        return ("SYNTAX_ERROR" if teacher.get("final_code_extracted")
                else "INVALID_SUBMISSION")
    return None


def teacher_final_natural_language(raw_response: str, code: str | None) -> str:
    if not raw_response:
        return ""
    without_fences = re.sub(r"```python\s*.*?```", "", raw_response,
                            flags=re.IGNORECASE | re.DOTALL)
    if code:
        without_fences = without_fences.replace(code, "")
    return without_fences.strip()


def parse_organizer_record(raw: str, *, final_error_type: str,
                           code_artifact: str, code_sha256: str,
                           planning_artifact: str,
                           failure_analysis_artifact: str,
                           sources: dict[str, SourceArtifact],
                           full_code: str) -> FailureFrontierRecord:
    return parse_organizer_record_with_audit(
        raw, final_error_type=final_error_type,
        code_artifact=code_artifact, code_sha256=code_sha256,
        planning_artifact=planning_artifact,
        failure_analysis_artifact=failure_analysis_artifact,
        sources=sources, full_code=full_code,
    ).record


def parse_organizer_record_with_audit(
    raw: str, *, final_error_type: str, code_artifact: str,
    code_sha256: str, planning_artifact: str,
    failure_analysis_artifact: str, sources: dict[str, SourceArtifact],
    full_code: str,
) -> OrganizerParseResult:
    text = raw.strip()
    match = re.fullmatch(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("FF organizer must return one JSON object") from error
    if not isinstance(data, dict):
        raise ValueError("FF organizer record must be an object")
    forbidden_keys = {"direct_facts", "full_code", "teacher_planning",
                      "teacher_failure_analysis", "next_directions",
                      "recommended_fix", "algorithm_recommendation"}
    if forbidden_keys & set(data):
        raise ValueError("FF organizer returned a forbidden field")
    raw_serialized = stable_json(data)
    if full_code and full_code in raw_serialized:
        raise ValueError("FF record duplicates the full submitted code")
    lowered = raw_serialized.lower()
    for phrase in FORBIDDEN_RECORD_GUIDANCE:
        if phrase in lowered:
            raise ValueError("FF record contains prohibited guidance or code")
    _reject_detailed_evaluation(raw_serialized)

    raw_excerpts = data.get("selected_low_confidence_excerpts", [])
    if not isinstance(raw_excerpts, list):
        raise ValueError("selected_low_confidence_excerpts must be an array")
    if len(raw_excerpts) > 8:
        raise ValueError("at most eight selected low-confidence excerpts")
    accepted: list[SelectedLowConfidenceExcerpt] = []
    rejected: list[RejectedLowConfidenceExcerpt] = []
    for index, raw_item in enumerate(raw_excerpts):
        if not isinstance(raw_item, dict):
            raise ValueError("selected excerpt must be an object")
        try:
            item = SelectedLowConfidenceExcerpt(**raw_item)
        except TypeError as error:
            raise ValueError("selected excerpt has an invalid schema") from error
        if item.source_type == "FF_ORGANIZER_HYPOTHESIS":
            raise ValueError("organizer hypotheses use their dedicated section")
        source = sources.get(item.source_type)
        if source is None:
            raise ValueError("selected excerpt has no registered raw source")
        if item.source_type != source.source_type:
            raise ValueError("low-confidence source type mismatch")
        if item.source_artifact != source.source_artifact:
            raise ValueError("low-confidence source artifact mismatch")
        if item.source_sha256 != source.source_sha256:
            raise ValueError("low-confidence source hash mismatch")
        if item.exact_source_excerpt not in source.content:
            rejected.append(RejectedLowConfidenceExcerpt(
                received_index=index,
                reason_code="NOT_VERBATIM_SUBSTRING",
                reason=("exact_source_excerpt is not an exact Unicode substring "
                        "of the registered source content"),
                source_type=item.source_type,
                source_artifact=item.source_artifact,
                source_sha256=item.source_sha256,
                exact_source_excerpt=item.exact_source_excerpt,
                confidence_note=item.confidence_note,
            ))
            continue
        accepted.append(item)

    data = dict(data)
    data["selected_low_confidence_excerpts"] = [
        asdict(item) for item in accepted
    ]
    data.update({
        "policy_version": FAILURE_FRONTIER_POLICY,
        "final_error_type": final_error_type,
        "code_artifact": code_artifact,
        "code_sha256": code_sha256,
        "planning_artifact": planning_artifact,
        "failure_analysis_artifact": failure_analysis_artifact,
    })
    record = FailureFrontierRecord.from_dict(data)
    return OrganizerParseResult(
        record=record,
        received_excerpt_count=len(raw_excerpts),
        rejected_excerpts=tuple(rejected),
    )


def render_ff_record(record: FailureFrontierRecord) -> str:
    lines = [
        "FAILURE FRONTIER RECORD",
        "",
        "## 1. DIRECT_FACT REFERENCES",
        "",
        f"Final submission error type: {record.final_error_type}",
        f"Teacher submitted-code artifact: {record.code_artifact}",
        f"Teacher submitted-code SHA-256: {record.code_sha256}",
        f"Teacher Planning artifact: {record.planning_artifact}",
        f"Teacher failure-analysis artifact: {record.failure_analysis_artifact}",
        "Fact boundary notice: This section contains only references to raw "
        "objective records and no natural-language interpretation.",
        "", "## 2. EVIDENCE_GROUNDED_INFERENCE", "",
    ]
    if not record.evidence_grounded_inferences:
        lines.append("None supported by the available materials.")
    for index, item in enumerate(record.evidence_grounded_inferences, 1):
        lines.extend([
            f"Inference E{index}", f"Claim: {item.claim}",
            f"Evidence: {item.evidence}",
            "Evidence source: " + " | ".join(item.evidence_sources),
            f"Organizer source: {item.organizer_source}",
            f"Support status: {item.support_status}",
            f"Reproducibility note: {item.reproducibility_note}", "",
        ])
    lines.extend(["## 3. LOW_CONFIDENCE_HYPOTHESIS", ""])
    if not (record.selected_low_confidence_excerpts or record.organizer_hypotheses):
        lines.append("None supported by the available materials.")
    for index, item in enumerate(record.selected_low_confidence_excerpts, 1):
        lines.extend([
            f"Hypothesis L{index}", f"Source type: {item.source_type}",
            f"Source artifact: {item.source_artifact}",
            f"Source SHA-256: {item.source_sha256}",
            f"Exact source excerpt: {item.exact_source_excerpt}",
            f"Confidence note: {item.confidence_note}", "",
        ])
    start = len(record.selected_low_confidence_excerpts)
    for index, item in enumerate(record.organizer_hypotheses, start + 1):
        lines.extend([
            f"Hypothesis L{index}", f"Source type: {item.source_type}",
            f"Organizer hypothesis: {item.hypothesis}",
            f"Evidence limitation: {item.evidence_limitation}", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_shared_failure_payload(*, final_error_type: str, code: str,
                                  code_artifact: str,
                                  planning: SourceArtifact,
                                  final_natural_language: SourceArtifact,
                                  failure_analysis: SourceArtifact,
                                  record: FailureFrontierRecord) -> str:
    code_hash = sha256_text(code)
    if code_hash != record.code_sha256:
        raise ValueError("submitted-code hash differs from FF record")
    blocks = [
        '<DIRECT_FACT_SOURCE type="FINAL_ERROR_TYPE">\n'
        f'{final_error_type}\n</DIRECT_FACT_SOURCE>',
        '<DIRECT_FACT_SOURCE type="TEACHER_SUBMITTED_CODE">\n'
        f'Artifact: {code_artifact}\nCode SHA-256: {code_hash}\n\n'
        f'The following is the exact submitted code:\n```python\n{code}\n```\n'
        '</DIRECT_FACT_SOURCE>',
        _render_low_source(planning),
        _render_low_source(final_natural_language),
        _render_low_source(failure_analysis),
        '<FAILURE_FRONTIER_RECORD>\n' + render_ff_record(record).rstrip() +
        '\n</FAILURE_FRONTIER_RECORD>',
    ]
    payload = "\n\n".join(blocks) + "\n"
    if payload.count(code) != 1:
        raise ValueError("full submitted code must occur exactly once")
    return payload


def render_flat_failure_payload(*, final_error_type: str, code: str,
                                code_artifact: str,
                                planning: SourceArtifact,
                                final_natural_language: SourceArtifact,
                                failure_analysis: SourceArtifact,
                                record: FailureFrontierRecord) -> str:
    """Render the same v2 evidence without confidence-tier framing.

    The Flat FF condition receives every raw source and every organizer-record
    field available to Direct/Critical FF.  Only the provenance tier labels,
    confidence notices, and tiered grouping are removed.  This is a
    deterministic presentation transform and performs no model call.
    """
    code_hash = sha256_text(code)
    if code_hash != record.code_sha256:
        raise ValueError("submitted-code hash differs from FF record")
    lines = [
        "FAILURE MATERIALS",
        "",
        "Final submission error type:",
        final_error_type,
        "",
        "Teacher submitted code:",
        f"Artifact: {code_artifact}",
        f"Code SHA-256: {code_hash}",
        "```python",
        code,
        "```",
    ]
    for source in (planning, final_natural_language, failure_analysis):
        lines.extend([
            "",
            "Source material:",
            f"Source type: {source.source_type}",
            f"Original artifact: {source.source_artifact}",
            f"Original artifact SHA-256: {source.source_sha256}",
            "Verbatim content:",
            source.content,
        ])
    lines.extend([
        "",
        "Organizer record:",
        f"Final submission error type: {record.final_error_type}",
        f"Teacher submitted-code artifact: {record.code_artifact}",
        f"Teacher submitted-code SHA-256: {record.code_sha256}",
        f"Teacher Planning artifact: {record.planning_artifact}",
        f"Teacher failure-analysis artifact: {record.failure_analysis_artifact}",
    ])
    item_number = 0
    for item in record.evidence_grounded_inferences:
        item_number += 1
        lines.extend([
            "", f"Organizer item {item_number}",
            f"Claim: {item.claim}",
            f"Evidence: {item.evidence}",
            "Evidence source: " + " | ".join(item.evidence_sources),
            f"Organizer source: {item.organizer_source}",
            f"Support status: {item.support_status}",
            f"Reproducibility note: {item.reproducibility_note}",
        ])
    for item in record.selected_low_confidence_excerpts:
        item_number += 1
        lines.extend([
            "", f"Organizer item {item_number}",
            f"Source type: {item.source_type}",
            f"Source artifact: {item.source_artifact}",
            f"Source SHA-256: {item.source_sha256}",
            f"Exact source excerpt: {item.exact_source_excerpt}",
            f"Confidence note: {item.confidence_note}",
        ])
    for item in record.organizer_hypotheses:
        item_number += 1
        lines.extend([
            "", f"Organizer item {item_number}",
            f"Source type: {item.source_type}",
            f"Organizer hypothesis: {item.hypothesis}",
            f"Evidence limitation: {item.evidence_limitation}",
        ])
    if item_number == 0:
        lines.extend(["", "Organizer items: None."])
    payload = "\n".join(lines).rstrip() + "\n"
    if payload.count(code) != 1:
        raise ValueError("full submitted code must occur exactly once")
    return payload


def render_student_input(problem: str, instruction: str, payload: str) -> str:
    return (
        f"{problem.rstrip()}\n\n# Condition Instruction\n\n{instruction.strip()}\n\n"
        f"# Shared Failure Materials\n\n{payload.rstrip()}\n"
    )


def validate_direct_instruction(instruction: str) -> None:
    lowered = instruction.lower()
    hits = [phrase for phrase in DIRECT_AUDIT_PHRASES if phrase in lowered]
    if hits:
        raise ValueError("Direct FF contains a source-audit instruction: " + hits[0])


def validate_no_detailed_evaluation(text: str) -> None:
    _reject_detailed_evaluation(text)


def _render_low_source(source: SourceArtifact) -> str:
    notice = (
        "The following text is model-generated natural language. It is "
        "unverified and is not an objective fact."
    )
    return (
        f'<LOW_CONFIDENCE_SOURCE type="{source.source_type}">\n'
        f'Confidence notice: {notice}\n'
        f'Original artifact: {source.source_artifact}\n'
        f'Original artifact SHA-256: {source.source_sha256}\n\n'
        f'Verbatim content:\n{source.content}\n'
        f'</LOW_CONFIDENCE_SOURCE>'
    )


def _reject_detailed_evaluation(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_DETAILED_EVALUATION:
        if phrase in lowered:
            raise ValueError("detailed evaluation information is model-visible")
