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
    def minCost(self, houses: List[int], cost: List[List[int]], m: int, n: int, target: int) -> int:
        INF=10**18; dp={(0,0):0}
        for i in range(m):
            nd={}
            colors=[houses[i]] if houses[i] else range(1,n+1)
            for (last,groups),v in dp.items():
                for c in colors:
                    ng=groups+(c!=last)
                    if ng<=target:
                        nv=v+(0 if houses[i] else cost[i][c-1]); key=(c,ng)
                        nd[key]=min(nd.get(key,INF),nv)
            dp=nd
        ans=min((v for (c,g),v in dp.items() if g==target),default=INF)
        return -1 if ans==INF else ans
