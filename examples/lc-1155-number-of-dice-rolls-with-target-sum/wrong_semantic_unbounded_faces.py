from math import comb

class Solution:
    def numRollsToTarget(self, n, k, target):
        return comb(target - 1, n - 1) if n <= target else 0
