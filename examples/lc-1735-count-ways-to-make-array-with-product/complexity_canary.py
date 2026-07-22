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
    def waysToFillArray(self, queries: List[List[int]]) -> List[int]:
        def solve(n,k):
            def dfs(pos,remaining):
                if pos==n: return int(remaining==1)
                total=0
                for d in range(1,remaining+1):
                    if remaining%d==0: total+=dfs(pos+1,remaining//d)
                return total
            return dfs(0,k)%MOD
        return [solve(n,k) for n,k in queries]
