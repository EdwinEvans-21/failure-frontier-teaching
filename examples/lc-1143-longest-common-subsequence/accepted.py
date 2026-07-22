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
    def longestCommonSubsequence(self, text1: str, text2: str) -> int:
        if len(text1) < len(text2): text1, text2 = text2, text1
        dp = [0] * (len(text2) + 1)
        for a in text1:
            prev = 0
            for j, b in enumerate(text2, 1):
                old = dp[j]
                if a == b: dp[j] = prev + 1
                elif dp[j-1] > dp[j]: dp[j] = dp[j-1]
                prev = old
        return dp[-1]
