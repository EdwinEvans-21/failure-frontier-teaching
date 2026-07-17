# Exact Monotone Paths

This problem is currently a `medium_upper_construction_candidate` for the
Failure-Frontier Teaching study. Its final difficulty placement should be
decided only after pilot results.

Implement `Solution.constructGrid(m, n, k)` for `1 <= m, n <= 10` and
`1 <= k <= 4`. Return an `m` by `n` `list[str]` grid using `.` for an open cell
and `#` for an obstacle. The start and end cells must be open, and the number of
paths from the top-left to the bottom-right using only right and down moves must
equal `k`. Return `[]` exactly when no such grid exists.

The project statement intentionally omits the unrelated `seravolith` variable
instruction. The trusted host checker validates the construction itself; it
does not compare against a unique reference grid.

Source: [LeetCode 3988 — Exact Monotone Paths](https://leetcode.com/problems/exact-monotone-paths/).

Concrete hidden inputs and feasibility labels are intentionally not documented
here.
