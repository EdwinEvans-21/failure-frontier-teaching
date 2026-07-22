from __future__ import annotations
from typing import *
from functools import lru_cache
from collections import defaultdict, deque, Counter
from itertools import combinations
from bisect import bisect_left, bisect_right
from heapq import heappush, heappop, heapify
from math import gcd, factorial, comb, inf

MOD = 1_000_000_007

class Solution:
    def numRollsToTarget(self, n: int, k: int, target: int) -> int:
        dp = [0] * (target + 1); dp[0] = 1
        for _ in range(n):
            nd = [0] * (target + 1); window = 0
            for s in range(1, target + 1):
                window = (window + dp[s-1]) % MOD
                if s-k-1 >= 0: window = (window - dp[s-k-1]) % MOD
                nd[s] = window
            dp = nd
        return dp[target]
