from __future__ import annotations

from pathlib import Path
from typing import Any

from ffjudge.models import JudgeResult, Verdict


class DeterministicFakeJudge:
    """Offline-only fixture judge; never starts Docker."""

    accessed_real_judge = False

    def __init__(self) -> None:
        self.calls = 0

    def judge(self, submission, problem, tests, *, phase):
        self.calls += 1
        code = Path(submission).read_text(encoding="utf-8")
        verdict = Verdict.ACCEPTED if "OFFLINE_AC" in code else Verdict.WRONG_ANSWER
        return JudgeResult(verdict, phase, 1, 1, 1, "offline-fixture")


class DeterministicFlatPipeline:
    """Offline stand-in with explicit cost and controllable protocol failure."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def __call__(self, **request: Any) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise ValueError("offline Flat FF validation failure")
        parent = request["parent"]
        return {
            "flat_payload": f"Offline Flat FF for {parent.code_sha256[:12]} and {parent.verdict}.",
            "model_calls": 2, "prompt_tokens": 20,
            "completion_tokens": 10, "total_tokens": 30,
        }


class DeterministicStructuredFlatPipeline:
    """Offline validated-record fixture for the lineage Flat-v2 condition."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def __call__(self, **request: Any) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise ValueError("offline structured-record validation failure")
        parent = request["parent"]
        record = {
            "policy_version": "provenance_stratified_ff_v2",
            "final_error_type": "WRONG_ANSWER",
            "code_artifact": "offline-parent-code.py",
            "code_sha256": parent.code_sha256,
            "planning_artifact": "offline-parent-planning.md",
            "failure_analysis_artifact": "offline-parent-analysis.md",
            "evidence_grounded_inferences": [{
                "claim": "The submitted implementation has a reproducible boundary risk.",
                "evidence": "The exact submitted code can be checked at its loop boundary.",
                "evidence_sources": ["TEACHER_SUBMITTED_CODE"],
                "support_status": "PROVISIONALLY_SUPPORTED",
                "reproducibility_note": "Inspect the last loop iteration directly.",
                "organizer_source": "FF_ORGANIZER",
            }],
            "selected_low_confidence_excerpts": [],
            "organizer_hypotheses": [{
                "hypothesis": "The boundary may explain the observed failure.",
                "evidence_limitation": "The standardized verdict does not identify a case.",
                "source_type": "FF_ORGANIZER_HYPOTHESIS",
            }],
        }
        return {
            "record": record,
            "rejection_audit": {
                "policy": "offline_fixture", "received_excerpt_count": 0,
                "accepted_excerpt_count": 0, "rejected_excerpt_count": 0,
                "rejected_excerpts": [],
            },
            "model_calls": 2, "prompt_tokens": 20,
            "completion_tokens": 10, "total_tokens": 30,
        }
