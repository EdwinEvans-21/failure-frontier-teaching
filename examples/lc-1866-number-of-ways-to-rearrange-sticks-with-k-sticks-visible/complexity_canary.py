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
    def rearrangeSticks(self, n: int, k: int) -> int:
        dp=[[0]*(k+1) for _ in range(n+1)];dp[0][0]=1
        facts=[1]*(n+1)
        for i in range(1,n+1):facts[i]=facts[i-1]*i%MOD
        for size in range(1,n+1):
            for visible in range(1,min(size,k)+1):
                total=0
                for before in range(visible-1,size):
                    total += comb(size-1,before)*dp[before][visible-1]*facts[size-1-before]
                dp[size][visible]=total%MOD
        return dp[n][k]
