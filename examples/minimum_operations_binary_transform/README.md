# Minimum Operations to Transform Binary String

This experiment problem is based on
[LeetCode 3980](https://leetcode.com/problems/minimum-operations-to-transform-binary-string/)
and uses a short project-owned statement.

Given two non-empty binary strings `s1` and `s2` of the same length, transform
`s1` into `s2` using the fewest operations.  One operation may either change a
single `0` to `1`, or change one adjacent `11` pair to `00`.  Return the minimum
number of operations, or `-1` if the target cannot be reached.

Implement `Solution.minOperations(s1, s2)`.  The input length is at most
100,000 and the result must be an integer.  This is a `medium_dp_candidate`:
its purpose is to distinguish a linear dynamic program from incomplete greedy
rules and state-space search that does not scale.

The public suite contains only a few protocol examples.  Concrete hidden
inputs, optimal operation sequences, and intermediate dynamic-programming
states are intentionally not documented or returned in model feedback.
