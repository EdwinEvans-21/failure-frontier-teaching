class Solution:
    def minOrAfterOperations(self, nums, k):
        answer = 0
        forbidden = 0
        for bit in range(29, -1, -1):
            trial = forbidden | (1 << bit)
            groups = 0
            running = (1 << 30) - 1
            for value in nums:
                running &= value
                if running & trial == 0:
                    groups += 1
                    running = (1 << 30) - 1
            if len(nums) - groups <= k:
                forbidden = trial
            else:
                answer |= 1 << bit
        return answer
