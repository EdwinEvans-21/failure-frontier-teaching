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
    def largestPathValue(self, colors: str, edges: List[List[int]]) -> int:
        n=len(colors);g=[[] for _ in range(n)]
        for a,b in edges:g[a].append(b)
        state=[0]*n
        def cycle(u):
            if state[u]==1:return True
            if state[u]==2:return False
            state[u]=1
            if any(cycle(v) for v in g[u]):return True
            state[u]=2;return False
        if any(cycle(i) for i in range(n) if state[i]==0):return -1
        best=0
        def paths(u,cnt):
            nonlocal best
            cnt=cnt.copy();cnt[ord(colors[u])-97]+=1;best=max(best,max(cnt))
            for v in g[u]:paths(v,cnt)
        indeg=[0]*n
        for a,b in edges:indeg[b]+=1
        for i in range(n):
            if indeg[i]==0:paths(i,[0]*26)
        return best
