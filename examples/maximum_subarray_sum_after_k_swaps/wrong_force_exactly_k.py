class Solution:

    def maxSum(self, nums: list[int], k: int) -> int:
        answer = nums[0]
        for left in range(len(nums)):
            for right in range(left, len(nums)):
                inside = sorted(nums[left:right + 1])
                outside = sorted(
                    nums[:left] + nums[right + 1:], reverse=True
                )
                swaps = min(k, len(inside), len(outside))
                answer = max(
                    answer,
                    sum(inside)
                    + sum(outside[index] - inside[index]
                          for index in range(swaps)),
                )
        return answer
