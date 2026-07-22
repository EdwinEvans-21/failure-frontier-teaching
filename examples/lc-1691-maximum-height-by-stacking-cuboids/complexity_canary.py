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
    def maxHeight(self, cuboids: List[List[int]]) -> int:
        orientations=[list(set(permutations(c))) for c in cuboids]
        @lru_cache(None)
        def dfs(mask, bx, by, bz):
            best=0
            for i,ors in enumerate(orientations):
                if mask>>i&1: continue
                for x,y,z in ors:
                    if x<=bx and y<=by and z<=bz:
                        best=max(best,z+dfs(mask|1<<i,x,y,z))
            return best
        M=10**9
        return dfs(0,M,M,M)
