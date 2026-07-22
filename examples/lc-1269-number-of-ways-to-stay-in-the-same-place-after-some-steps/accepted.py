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
    def numWays(self, steps: int, arrLen: int) -> int:
        width=min(arrLen,steps//2+1); dp=[0]*width; dp[0]=1
        for _ in range(steps):
            nd=[0]*width
            for i,x in enumerate(dp):
                nd[i]=(nd[i]+x)%MOD
                if i: nd[i-1]=(nd[i-1]+x)%MOD
                if i+1<width: nd[i+1]=(nd[i+1]+x)%MOD
            dp=nd
        return dp[0]
