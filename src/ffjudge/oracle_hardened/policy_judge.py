from __future__ import annotations

from pathlib import Path

from ..models import JudgeResult, Verdict
from ..runner import DockerJudge

from .catalog import PROBLEMS
from .generators import generate_cases, stress_cases
from .judge import OracleHardenedJudge


POLICY_VERSION = "judge_v3_oracle_hardened_mixed31_v1"

_VERDICTS = {
    "AC": Verdict.ACCEPTED,
    "WA": Verdict.WRONG_ANSWER,
    "RE": Verdict.RUNTIME_ERROR,
    "CE": Verdict.SYNTAX_ERROR,
    "TLE": Verdict.TIME_LIMIT_EXCEEDED,
    "MLE": Verdict.MEMORY_LIMIT_EXCEEDED,
    "INVALID_SUBMISSION": Verdict.INVALID_SUBMISSION,
    "INTERNAL_ERROR": Verdict.INTERNAL_ERROR,
}


class OracleHardenedPolicyJudge:
    """Pilot-compatible v3 Judge.

    The 16 audited problems use deterministic oracle differential plus stress.
    The other 15 retain their frozen hidden tests and additionally run their
    frozen stress suite after hidden AC.  The mixed status is explicit and is
    not represented as uniform 31-problem hardening.
    """

    policy_version = POLICY_VERSION

    def __init__(self, image: str = "ffjudge-python:latest") -> None:
        self.image = image
        self.hardened = OracleHardenedJudge(image)
        self.legacy = DockerJudge(image)
        self._semantic_cases: dict[int, list[dict]] = {}
        self._stress_cases: dict[int, list[dict]] = {}

    def judge(self, submission, problem, tests, *, phase="hidden") -> JudgeResult:
        problem_path = Path(problem)
        problem_id = problem_path.parent.name
        try:
            number = int(problem_id[3:7])
        except (ValueError, IndexError):
            return self.legacy.judge(submission, problem, tests, phase=phase)
        if number not in PROBLEMS:
            hidden = self.legacy.judge(submission, problem, tests, phase=phase)
            if hidden.verdict != Verdict.ACCEPTED:
                return hidden
            stress_path = problem_path.parent / "stress_tests.json"
            if not stress_path.is_file():
                return hidden
            stress = self.legacy.judge(submission, problem, stress_path, phase="hidden")
            if stress.verdict == Verdict.ACCEPTED:
                return JudgeResult(Verdict.ACCEPTED, phase, hidden.passed + stress.passed,
                                   hidden.total + stress.total,
                                   hidden.runtime_ms + stress.runtime_ms,
                                   "All hidden and stress tests passed.", None)
            return stress
        if number not in self._semantic_cases:
            self._semantic_cases[number] = generate_cases(number)
        semantic_cases = self._semantic_cases[number]
        semantic = self.hardened.judge(Path(submission), problem_path,
                                       semantic_cases, layer="semantic")
        if semantic["verdict"] != "AC":
            return self._convert(semantic, phase)
        if number not in self._stress_cases:
            self._stress_cases[number] = stress_cases(number)
        generated_stress = self._stress_cases[number]
        stress = self.hardened.judge(Path(submission), problem_path,
                                     generated_stress, layer="complexity_stress")
        if stress["verdict"] != "AC":
            return self._convert(stress, phase)
        return JudgeResult(Verdict.ACCEPTED, phase,
                           int(semantic.get("passed", 0)) + int(stress.get("passed", 0)),
                           int(semantic.get("passed", 0)) + int(stress.get("passed", 0)),
                           int(semantic.get("runtime_ms", 0)) + int(stress.get("runtime_ms", 0)),
                           "All oracle-hardened semantic and stress tests passed.", None)

    @staticmethod
    def _convert(result, phase: str) -> JudgeResult:
        verdict = _VERDICTS.get(result.get("verdict"), Verdict.INTERNAL_ERROR)
        message = {
            Verdict.WRONG_ANSWER: "A hidden case failed.",
            Verdict.RUNTIME_ERROR: "Submission failed during execution.",
            Verdict.SYNTAX_ERROR: "Submission contains invalid Python syntax.",
            Verdict.TIME_LIMIT_EXCEEDED: "Execution exceeded the time limit.",
            Verdict.MEMORY_LIMIT_EXCEEDED: "Execution exceeded the memory limit.",
            Verdict.INVALID_SUBMISSION: "Submission entrypoint is invalid.",
            Verdict.INTERNAL_ERROR: "The v3 Judge could not complete.",
        }.get(verdict, "All tests passed.")
        return JudgeResult(verdict, phase, 0, 1,
                           int(result.get("runtime_ms", 0)), message, None)
