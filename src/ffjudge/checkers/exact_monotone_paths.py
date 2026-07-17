from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckerResult:
    passed: bool
    failure_category: str | None = None


def _failure(category: str) -> CheckerResult:
    return CheckerResult(False, category)


def _parse_trusted_case(
    args: list[Any], kwargs: dict[str, Any], oracle: dict[str, Any]
) -> tuple[int, int, int, bool] | None:
    if kwargs or len(args) != 3:
        return None
    m, n, k = args
    if type(m) is not int or type(n) is not int or type(k) is not int:
        return None
    if not (1 <= m <= 10 and 1 <= n <= 10 and 1 <= k <= 4):
        return None
    if not isinstance(oracle, dict) or type(oracle.get("feasible")) is not bool:
        return None
    return m, n, k, oracle["feasible"]


def _count_paths(grid: list[str], m: int, n: int) -> int:
    dp = [[0 for _ in range(n)] for _ in range(m)]
    dp[0][0] = 1
    for row in range(m):
        for column in range(n):
            if grid[row][column] == "#":
                dp[row][column] = 0
                continue
            if row == 0 and column == 0:
                continue
            from_above = dp[row - 1][column] if row > 0 else 0
            from_left = dp[row][column - 1] if column > 0 else 0
            dp[row][column] = from_above + from_left
    return dp[m - 1][n - 1]


def check_exact_monotone_paths(
    actual: Any,
    args: list[Any],
    kwargs: dict[str, Any],
    oracle: dict[str, Any],
) -> CheckerResult:
    trusted_case = _parse_trusted_case(args, kwargs, oracle)
    if trusted_case is None:
        return _failure("invalid_oracle_data")
    m, n, k, feasible = trusted_case

    if actual == []:
        if feasible:
            return _failure("unexpected_empty")
        return CheckerResult(True)

    if type(actual) is not list:
        return _failure("invalid_return_type")
    if len(actual) != m:
        return _failure("invalid_row_count")
    if any(type(row) is not str for row in actual):
        return _failure("invalid_row_type")
    if any(len(row) != n for row in actual):
        return _failure("invalid_column_count")
    if any(cell not in {".", "#"} for row in actual for cell in row):
        return _failure("invalid_character")
    if actual[0][0] != ".":
        return _failure("blocked_start")
    if actual[m - 1][n - 1] != ".":
        return _failure("blocked_end")

    if _count_paths(actual, m, n) != k:
        return _failure("path_count_mismatch")
    if not feasible:
        return _failure("oracle_contradiction")
    return CheckerResult(True)


__all__ = ["CheckerResult", "check_exact_monotone_paths"]
