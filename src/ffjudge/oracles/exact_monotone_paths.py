from __future__ import annotations

from math import comb


def is_feasible(m: int, n: int, k: int) -> bool:
    if k == 1:
        return True
    if k == 2:
        return m >= 2 and n >= 2
    if k == 3:
        return min(m, n) >= 2 and max(m, n) >= 3
    if k == 4:
        return min(m, n) >= 3 or (
            min(m, n) == 2 and max(m, n) >= 4
        )
    raise ValueError("k must be between 1 and 4")


def binomial_capacity(m: int, n: int) -> int:
    return comb(m + n - 2, m - 1)


def _open_rectangle(grid: list[list[str]], height: int, width: int) -> None:
    for row in range(height):
        for column in range(width):
            grid[row][column] = "."


def construct_reference_grid(m: int, n: int, k: int) -> list[str]:
    if not (1 <= m <= 10 and 1 <= n <= 10 and 1 <= k <= 4):
        raise ValueError("m, n, or k is outside the supported constraint")
    if not is_feasible(m, n, k):
        return []

    grid = [["#" for _ in range(n)] for _ in range(m)]
    if k == 1:
        height, width = 1, 1
        grid[0][0] = "."
    elif k == 2:
        height, width = 2, 2
        _open_rectangle(grid, height, width)
    elif k == 3:
        if n >= 3:
            height, width = 2, 3
        else:
            height, width = 3, 2
        _open_rectangle(grid, height, width)
    elif min(m, n) == 2:
        if n >= 4:
            height, width = 2, 4
        else:
            height, width = 4, 2
        _open_rectangle(grid, height, width)
    else:
        height, width = 3, 3
        _open_rectangle(grid, height, width)
        grid[0][2] = "#"
        grid[2][0] = "#"

    endpoint_row = height - 1
    endpoint_column = width - 1
    for column in range(endpoint_column, n):
        grid[endpoint_row][column] = "."
    for row in range(endpoint_row, m):
        grid[row][n - 1] = "."
    return ["".join(row) for row in grid]


__all__ = ["binomial_capacity", "construct_reference_grid", "is_feasible"]
