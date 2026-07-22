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
    def secondMinimum(self, n: int, edges: List[List[int]], time: int, change: int) -> int:
        g=[[] for _ in range(n+1)]
        for u,v in edges:g[u].append(v);g[v].append(u)
        dist=[[inf,inf] for _ in range(n+1)];dist[1][0]=0;q=deque([(1,0)])
        while q:
            u,d=q.popleft()
            depart=d
            if (depart//change)%2:depart=(depart//change+1)*change
            nd=depart+time
            for v in g[u]:
                if nd<dist[v][0]:dist[v][1]=dist[v][0];dist[v][0]=nd;q.append((v,nd))
                elif dist[v][0]<nd<dist[v][1]:dist[v][1]=nd;q.append((v,nd))
        return dist[n][1]
