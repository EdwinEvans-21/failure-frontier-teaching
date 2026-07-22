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
    def numberOfWays(self, corridor: str) -> int:
        n=len(corridor)
        @lru_cache(None)
        def dfs(start):
            seats=0;total=0
            for end in range(start,n):
                seats+=corridor[end]=='S'
                if seats>2:break
                if seats==2:
                    if end==n-1:total+=1
                    else:total+=dfs(end+1)
            return total%MOD
        return dfs(0)
