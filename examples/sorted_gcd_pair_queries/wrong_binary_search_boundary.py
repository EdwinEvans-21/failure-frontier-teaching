from bisect import bisect_left


class Solution:

    def gcdValues(self, nums: list[int], queries: list[int]) -> list[int]:
        maximum = max(nums)
        frequency = [0] * (maximum + 1)
        for value in nums:
            frequency[value] += 1

        exact = [0] * (maximum + 1)
        for divisor in range(1, maximum + 1):
            divisible = sum(
                frequency[multiple]
                for multiple in range(divisor, maximum + 1, divisor)
            )
            exact[divisor] = divisible * (divisible - 1) // 2
        for divisor in range(maximum, 0, -1):
            for multiple in range(divisor * 2, maximum + 1, divisor):
                exact[divisor] -= exact[multiple]

        prefix = [0]
        for count in exact[1:]:
            prefix.append(prefix[-1] + count)
        return [bisect_left(prefix, query) for query in queries]
