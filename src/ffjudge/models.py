from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import json


class Verdict(str, Enum):
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    INVALID_SUBMISSION = "INVALID_SUBMISSION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class Entrypoint:
    kind: str
    function: str | None = None
    class_name: str | None = None
    method: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entrypoint":
        entrypoint = cls(**data)
        if entrypoint.kind == "function" and not entrypoint.function:
            raise ValueError("function entrypoint requires 'function'")
        if entrypoint.kind == "class_method" and not (entrypoint.class_name
                                                      and entrypoint.method):
            raise ValueError(
                "class_method entrypoint requires 'class_name' and 'method'")
        if entrypoint.kind not in {"function", "class_method"}:
            raise ValueError(f"unsupported entrypoint kind: {entrypoint.kind}")
        return entrypoint


@dataclass(frozen=True)
class Limits:
    time_seconds: float = 2.0
    memory_mb: int = 256
    cpus: float = 1.0
    pids: int = 64

    def __post_init__(self) -> None:
        if self.time_seconds <= 0 or self.memory_mb <= 0 or self.cpus <= 0:
            raise ValueError("time, memory, and CPU limits must be positive")
        if self.pids <= 0:
            raise ValueError("PID limit must be positive")


@dataclass(frozen=True)
class ProblemSpec:
    problem_id: str
    title: str
    entrypoint: Entrypoint
    comparison: str = "exact"
    float_tolerance: float = 1e-6
    limits: Limits = Limits()
    difficulty: str = ""
    role: str = ""
    source_url: str = ""
    description: str = ""
    input_contract: str = ""
    output_contract: str = ""
    checker: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "ProblemSpec":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["entrypoint"] = Entrypoint.from_dict(data["entrypoint"])
        data["limits"] = Limits(**data.get("limits", {}))
        spec = cls(**data)
        if spec.comparison not in {"exact", "unordered", "float", "custom"}:
            raise ValueError(f"unsupported comparison mode: {spec.comparison}")
        if spec.comparison == "custom" and not spec.checker:
            raise ValueError("custom comparison requires 'checker'")
        if spec.comparison != "custom" and spec.checker:
            raise ValueError("checker is only valid for custom comparison")
        return spec

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JudgeResult:
    verdict: Verdict
    phase: str
    passed: int
    total: int
    runtime_ms: int
    message: str = ""
    case_index: int | None = None
    checker_failure_category: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JudgeResult":
        data = dict(data)
        data["verdict"] = Verdict(data["verdict"])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data

    def model_feedback(self) -> dict[str, Any]:
        """Return only information that may be shown to the code-generating model."""
        feedback: dict[str, Any] = {
            "verdict": self.verdict.value,
            "phase": self.phase,
            "message": self.message,
        }
        if self.phase == "public":
            feedback.update(
                passed=self.passed,
                total=self.total,
                case_index=self.case_index,
            )
        return feedback
