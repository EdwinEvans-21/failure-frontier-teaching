class Solution:

    def maxSum(self, nums: list[int], k: int) -> int:
        take = min(len(nums), 2 * k + 1)
        return sum(sorted(nums, reverse=True)[:take])
