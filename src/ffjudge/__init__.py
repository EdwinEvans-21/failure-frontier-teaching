"""Failure-Frontier local judge."""

from .models import JudgeResult, ProblemSpec, Verdict
from .runner import DockerJudge

__all__ = ["DockerJudge", "JudgeResult", "ProblemSpec", "Verdict"]
