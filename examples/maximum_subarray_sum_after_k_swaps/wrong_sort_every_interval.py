class Solution:

    def maxSum(self, nums: list[int], k: int) -> int:
        answer = nums[0]
        for left in range(len(nums)):
            for right in range(left, len(nums)):
                inside = sorted(nums[left:right + 1])
                outside = sorted(
                    nums[:left] + nums[right + 1:], reverse=True
                )
                gains = (
                    outside[index] - inside[index]
                    for index in range(min(k, len(inside), len(outside)))
                )
                answer = max(
                    answer,
                    sum(inside) + sum(gain for gain in gains if gain > 0),
                )
        return answer
