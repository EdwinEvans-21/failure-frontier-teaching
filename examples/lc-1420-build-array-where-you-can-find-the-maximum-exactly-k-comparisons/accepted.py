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
    def numOfArrays(self, n: int, m: int, k: int) -> int:
        dp=[[0]*(m+1) for _ in range(k+1)]
        for mx in range(1,m+1):dp[1][mx]=1
        for length in range(2,n+1):
            nd=[[0]*(m+1) for _ in range(k+1)]
            for c in range(1,k+1):
                prefix=0
                for mx in range(1,m+1):
                    prefix=(prefix+dp[c-1][mx-1])%MOD
                    nd[c][mx]=(dp[c][mx]*mx+prefix)%MOD
            dp=nd
        return sum(dp[k])%MOD
