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
    def secondMinimum(self, n: int, edges: List[List[int]], time: int, change: int) -> int:
        g=[[] for _ in range(n+1)]
        for a,b in edges:g[a].append(b);g[b].append(a)
        heap=[(0,1,(1,))];arrivals=[]
        while heap:
            now,u,path=heappop(heap)
            if u==n:
                if not arrivals or now!=arrivals[-1]:arrivals.append(now)
                if len(arrivals)==2:return now
            depart=now
            if (depart//change)%2:depart=(depart//change+1)*change
            nxt=depart+time
            for v in g[u]:
                heappush(heap,(nxt,v,path+(v,)))
        raise AssertionError
