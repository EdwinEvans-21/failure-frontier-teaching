from __future__ import annotations
from typing import *
from functools import lru_cache
from collections import defaultdict, deque, Counter
from itertools import combinations, permutations, product
from bisect import bisect_left, bisect_right
from heapq import heappush, heappop
from math import gcd, factorial, comb, inf, isqrt

MOD = 1_000_000_007

class Solution:
    def numWays(self, steps: int, arrLen: int) -> int:
        dp=[0]*arrLen; dp[0]=1
        for _ in range(steps):
            nd=[0]*arrLen
            for i in range(arrLen):
                nd[i]=dp[i]
                if i: nd[i]+=dp[i-1]
                if i+1<arrLen: nd[i]+=dp[i+1]
                nd[i]%=MOD
            dp=nd
        return dp[0]
