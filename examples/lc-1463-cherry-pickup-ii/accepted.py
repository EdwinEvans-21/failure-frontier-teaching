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
    def cherryPickup(self, grid: List[List[int]]) -> int:
        m,n=len(grid),len(grid[0]); neg=-10**15; dp=[[neg]*n for _ in range(n)];dp[0][n-1]=grid[0][0]+(grid[0][n-1] if n>1 else 0)
        for r in range(1,m):
            nd=[[neg]*n for _ in range(n)]
            for a in range(n):
                for b in range(n):
                    val=grid[r][a]+(grid[r][b] if a!=b else 0)
                    best=neg
                    for pa in (a-1,a,a+1):
                        for pb in (b-1,b,b+1):
                            if 0<=pa<n and 0<=pb<n:best=max(best,dp[pa][pb])
                    nd[a][b]=best+val
            dp=nd
        return max(map(max,dp))
