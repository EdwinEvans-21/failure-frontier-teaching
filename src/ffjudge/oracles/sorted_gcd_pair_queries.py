"""Trusted solvers for Sorted GCD Pair Queries."""

from __future__ import annotations

from bisect import bisect_right
from math import gcd


def _validate(nums: list[int], queries: list[int]) -> None:
    if not isinstance(nums, list) or len(nums) < 2:
        raise ValueError("nums must contain at least two values")
    if any(type(value) is not int or not 1 <= value <= 50_000
           for value in nums):
        raise ValueError("nums values must be integers in [1, 50000]")
    pair_count = len(nums) * (len(nums) - 1) // 2
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list")
    if any(type(query) is not int or not 0 <= query < pair_count
           for query in queries):
        raise ValueError("query is outside the zero-indexed pair range")


def gcd_values_reference(nums: list[int], queries: list[int]) -> list[int]:
    """Answer queries in O(V log V + Q log V) time and O(V) space."""

    _validate(nums, queries)
    maximum = max(nums)
    frequency = [0] * (maximum + 1)
    for value in nums:
        frequency[value] += 1

    exact = [0] * (maximum + 1)
    for divisor in range(1, maximum + 1):
        divisible = 0
        for multiple in range(divisor, maximum + 1, divisor):
            divisible += frequency[multiple]
        exact[divisor] = divisible * (divisible - 1) // 2

    for divisor in range(maximum, 0, -1):
        for multiple in range(divisor * 2, maximum + 1, divisor):
            exact[divisor] -= exact[multiple]

    prefix = [0] * (maximum + 1)
    for divisor in range(1, maximum + 1):
        prefix[divisor] = prefix[divisor - 1] + exact[divisor]

    return [bisect_right(prefix, query) for query in queries]


def gcd_values_bruteforce(nums: list[int], queries: list[int]) -> list[int]:
    """Independent small-input oracle that materializes and sorts every pair."""

    _validate(nums, queries)
    pairs = [
        gcd(nums[left], nums[right])
        for left in range(len(nums))
        for right in range(left + 1, len(nums))
    ]
    pairs.sort()
    return [pairs[query] for query in queries]
