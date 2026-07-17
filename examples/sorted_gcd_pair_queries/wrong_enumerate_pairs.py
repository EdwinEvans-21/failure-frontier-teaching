from math import gcd


class Solution:

    def gcdValues(self, nums: list[int], queries: list[int]) -> list[int]:
        pairs = [
            gcd(nums[left], nums[right])
            for left in range(len(nums))
            for right in range(left + 1, len(nums))
        ]
        pairs.sort()
        return [pairs[query] for query in queries]
