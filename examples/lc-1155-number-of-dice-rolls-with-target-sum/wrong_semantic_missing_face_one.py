class Solution:
    def numRollsToTarget(self, n, k, target):
        dp = [0] * (target + 1)
        dp[0] = 1
        for _ in range(n):
            next_dp = [0] * (target + 1)
            for total in range(target + 1):
                for face in range(2, k + 1):
                    if total >= face:
                        next_dp[total] += dp[total - face]
            dp = next_dp
        return dp[target] % 1_000_000_007
