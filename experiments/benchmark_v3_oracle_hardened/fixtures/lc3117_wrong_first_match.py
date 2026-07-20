class Solution:
    def minimumValueSum(self, nums, andValues):
        pos = 0
        total = 0
        for target in andValues:
            value = (1 << 30) - 1
            while pos < len(nums):
                value &= nums[pos]
                total += nums[pos]
                pos += 1
                if value == target:
                    break
            else:
                return -1
        return total if pos == len(nums) else -1
