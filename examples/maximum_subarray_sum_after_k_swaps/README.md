# Maximum Subarray Sum After at Most K Swaps

This experiment fixture is based on
[LeetCode 3962](https://leetcode.com/problems/maximum-subarray-sum-after-at-most-k-swaps/)
and uses a short project-owned statement.

Given an integer array `nums`, perform at most `k` swaps of any two positions.
Return the largest possible sum of a non-empty contiguous subarray after those
swaps.  Implement `Solution.maxSum(nums, k)`.

The contract is `1 <= len(nums) <= 1500`, values from -100000 through 100000,
and `0 <= k <= len(nums)`.  This `hard_optimization_candidate` targets an
interval enumeration combined with compressed order statistics; rebuilding and
sorting both sides independently for every interval is not expected to scale.

The public suite is deliberately small.  Concrete hidden arrays and answers,
optimal intervals or exchanged elements, swap gains, and data-structure state
are not included in documentation or model feedback.
