from bisect import bisect_right


class Solution:

    def gcdValues(self, nums: list[int], queries: list[int]) -> list[int]:
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
