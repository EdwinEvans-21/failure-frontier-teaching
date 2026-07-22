class Solution:
    def numRollsToTarget(self, n, k, target):
        # Coin-change style update: loses the die order and does not enforce n.
        dp = [0] * (target + 1)
        dp[0] = 1
        for face in range(1, k + 1):
            for total in range(face, target + 1):
                dp[total] += dp[total - face]
        return dp[target]
