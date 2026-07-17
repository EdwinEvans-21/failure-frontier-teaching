"""Trusted solvers for Minimum Operations for Binary String Transformation.

The linear solver is used to generate formal expected answers.  The BFS solver
is intentionally limited to small inputs and serves as an independent oracle.
"""

from __future__ import annotations

from collections import deque


def _validate_inputs(s1: str, s2: str) -> None:
    if not isinstance(s1, str) or not isinstance(s2, str):
        raise TypeError("s1 and s2 must be strings")
    if len(s1) != len(s2) or not s1:
        raise ValueError("s1 and s2 must have the same positive length")
    if any(bit not in "01" for bit in s1 + s2):
        raise ValueError("s1 and s2 must be binary strings")


def min_operations_reference(s1: str, s2: str) -> int:
    """Return the minimum operations in O(n) time and O(1) DP space.

    A selected path edge represents one adjacent ``11 -> 00`` operation.  Each
    position that must change from 1 to 0 has to be incident to a selected
    edge.  The two DP states record whether the edge from the left is selected.
    """

    _validate_inputs(s1, s2)
    infinity = len(s1) + 1
    dp = [0, infinity]

    for index, (source_bit, target_bit) in enumerate(zip(s1, s2)):
        must_decrease = source_bit == "1" and target_bit == "0"
        next_dp = [infinity, infinity]
        right_choices = (0,) if index == len(s1) - 1 else (0, 1)

        for selected_left in (0, 1):
            if dp[selected_left] == infinity:
                continue
            for selected_right in right_choices:
                if must_decrease and not (selected_left or selected_right):
                    continue
                candidate = dp[selected_left] + selected_right
                next_dp[selected_right] = min(
                    next_dp[selected_right], candidate
                )
        dp = next_dp

    selected_edges = dp[0]
    if selected_edges == infinity:
        return -1
    return s2.count("1") - s1.count("1") + 3 * selected_edges


def bfs_distances(s1: str) -> dict[str, int]:
    """Return directed shortest-path distances from a small binary string."""

    _validate_inputs(s1, s1)
    if len(s1) > 8:
        raise ValueError("the exhaustive BFS oracle is limited to n <= 8")

    distances = {s1: 0}
    queue = deque([s1])
    while queue:
        state = queue.popleft()
        distance = distances[state] + 1

        for index, bit in enumerate(state):
            if bit == "0":
                successor = state[:index] + "1" + state[index + 1:]
                if successor not in distances:
                    distances[successor] = distance
                    queue.append(successor)

        for index in range(len(state) - 1):
            if state[index:index + 2] == "11":
                successor = state[:index] + "00" + state[index + 2:]
                if successor not in distances:
                    distances[successor] = distance
                    queue.append(successor)

    return distances


def min_operations_bfs(s1: str, s2: str) -> int:
    """Return the exact small-input answer, or -1 when s2 is unreachable."""

    _validate_inputs(s1, s2)
    return bfs_distances(s1).get(s2, -1)
