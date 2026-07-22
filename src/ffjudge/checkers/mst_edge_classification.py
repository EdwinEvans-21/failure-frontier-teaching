from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckerResult:
    passed: bool
    failure_category: str | None = None


def _failure(category: str) -> CheckerResult:
    return CheckerResult(False, category)


def _normalize(value: Any) -> list[int] | None:
    if type(value) is not list:
        return None
    if any(type(item) is not int for item in value):
        return None
    return sorted(value)


def check_mst_edge_classification(
    actual: Any,
    args: list[Any],
    kwargs: dict[str, Any],
    oracle: dict[str, Any],
) -> CheckerResult:
    if kwargs or len(args) != 2:
        return _failure("invalid_arguments")
    if type(actual) is not list or len(actual) != 2:
        return _failure("invalid_return_type")
    if not isinstance(oracle, dict) or "classification" not in oracle:
        return _failure("invalid_oracle_data")
    expected = oracle["classification"]
    if type(expected) is not list or len(expected) != 2:
        return _failure("invalid_oracle_data")
    actual_critical = _normalize(actual[0])
    actual_pseudo = _normalize(actual[1])
    expected_critical = _normalize(expected[0])
    expected_pseudo = _normalize(expected[1])
    if (
        actual_critical is None
        or actual_pseudo is None
        or expected_critical is None
        or expected_pseudo is None
    ):
        return _failure("invalid_edge_list")
    if actual_critical != expected_critical or actual_pseudo != expected_pseudo:
        return _failure("classification_mismatch")
    return CheckerResult(True)


__all__ = ["CheckerResult", "check_mst_edge_classification"]
