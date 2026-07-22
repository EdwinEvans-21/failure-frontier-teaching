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
    def waysToBuildRooms(self, prevRoom: List[int]) -> int:
        n=len(prevRoom);g=[[] for _ in range(n)]
        for i in range(1,n):g[prevRoom[i]].append(i)
        fact=[1]*(n+1);inv=[1]*(n+1)
        for i in range(1,n+1):fact[i]=fact[i-1]*i%MOD
        inv[n]=pow(fact[n],MOD-2,MOD)
        for i in range(n,0,-1):inv[i-1]=inv[i]*i%MOD
        def dfs(u):
            size=1;ways=1
            for v in g[u]:
                sv,wv=dfs(v);ways=ways*wv%MOD*inv[sv]%MOD;size+=sv
            ways=ways*fact[size-1]%MOD
            return size,ways
        return dfs(0)[1]
