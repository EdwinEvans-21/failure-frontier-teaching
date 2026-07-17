from bisect import bisect_right


class Solution:

    def gcdValues(self, nums: list[int], queries: list[int]) -> list[int]:
        maximum = max(nums)
        frequency = [0] * (maximum + 1)
        for value in nums:
            frequency[value] += 1

        prefix = [0] * (maximum + 1)
        for divisor in range(1, maximum + 1):
            divisible = sum(
                frequency[multiple]
                for multiple in range(divisor, maximum + 1, divisor)
            )
            prefix[divisor] = (
                prefix[divisor - 1]
                + divisible * (divisible - 1) // 2
            )
        return [bisect_right(prefix, query) for query in queries]
