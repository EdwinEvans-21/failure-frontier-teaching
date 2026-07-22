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
    def tilingRectangle(self, n: int, m: int) -> int:
        if n > m: n,m=m,n
        heights=[0]*m; best=n*m
        def dfs(used:int):
            nonlocal best
            if used>=best:return
            low=min(heights)
            if low==n: best=used; return
            idx=heights.index(low); end=idx
            while end<m and heights[end]==low: end+=1
            maxs=min(n-low,end-idx)
            for s in range(maxs,0,-1):
                for j in range(idx,idx+s): heights[j]+=s
                dfs(used+1)
                for j in range(idx,idx+s): heights[j]-=s
        dfs(0); return best
