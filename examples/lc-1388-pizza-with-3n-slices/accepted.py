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
    def maxSizeSlices(self, slices: List[int]) -> int:
        choose=len(slices)//3
        def linear(a):
            n=len(a); dp=[[0]*(choose+1) for _ in range(n+1)]
            for i,x in enumerate(a,1):
                for c in range(1,choose+1):dp[i][c]=max(dp[i-1][c],x+(dp[i-2][c-1] if i>=2 else 0))
            return dp[n][choose]
        return max(linear(slices[:-1]),linear(slices[1:]))
