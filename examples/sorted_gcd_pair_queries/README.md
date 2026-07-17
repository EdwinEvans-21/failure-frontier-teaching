# Sorted GCD Pair Queries

This experiment fixture is based on
[LeetCode 3312](https://leetcode.com/problems/sorted-gcd-pair-queries/) and uses
a short project-owned statement.

Given an integer array `nums`, form the GCD of every pair of positions
`i < j` and sort those values.  For every zero-indexed entry in `queries`,
return the value at that position in the sorted multiset.  Implement
`Solution.gcdValues(nums, queries)`.

The contract is `2 <= len(nums) <= 100000`, values in `nums` are between 1 and
50000, and `1 <= len(queries) <= 100000`.  Every query is a valid index among
the `n * (n - 1) / 2` pairs.  This fixture is a `hard_number_theory_candidate`
intended to exercise divisor counting, inclusion-exclusion, large integer pair
counts, prefix sums, and binary-search boundaries.

The public suite is deliberately small.  Concrete hidden inputs and outputs,
GCD frequency or cumulative distributions, and failure locations are not
included in documentation or model feedback.
