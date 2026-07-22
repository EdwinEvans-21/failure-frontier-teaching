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
    def colorTheGrid(self, m: int, n: int) -> int:
        def rows():
            return [r for r in product(range(3),repeat=m) if all(r[i]!=r[i+1] for i in range(m-1))]
        dp={r:1 for r in rows()}
        for _ in range(1,n):
            current=rows(); previous=rows(); nd={r:0 for r in current}
            for r in current:
                for p in previous:
                    if all(r[i]!=p[i] for i in range(m)):nd[r]=(nd[r]+dp[p])%MOD
            dp=nd
        return sum(dp.values())%MOD
