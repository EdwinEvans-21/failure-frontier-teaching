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
    def rearrangeSticks(self, n: int, k: int) -> int:
        dp=[0]*(k+1);dp[0]=1
        for length in range(1,n+1):
            nd=[0]*(k+1)
            for visible in range(1,min(length,k)+1):
                nd[visible]=(dp[visible-1]+(length-1)*dp[visible])%MOD
            dp=nd
        return dp[k]
