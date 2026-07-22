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
    def numberWays(self, hats: List[List[int]]) -> int:
        n=len(hats); owners=[[] for _ in range(41)]
        for p,hs in enumerate(hats):
            for h in hs:owners[h].append(p)
        dp=[0]*(1<<n);dp[0]=1
        for h in range(1,41):
            nd=dp[:]
            for mask,v in enumerate(dp):
                if not v:continue
                for p in owners[h]:
                    if not mask>>p&1:nd[mask|1<<p]=(nd[mask|1<<p]+v)%MOD
            dp=nd
        return dp[-1]
