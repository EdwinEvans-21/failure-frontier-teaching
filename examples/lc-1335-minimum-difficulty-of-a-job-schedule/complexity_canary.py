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
    def minDifficulty(self, jobDifficulty: List[int], d: int) -> int:
        n=len(jobDifficulty)
        if n<d: return -1
        best=inf
        for cuts in combinations(range(1,n),d-1):
            p=(0,)+cuts+(n,)
            best=min(best,sum(max(jobDifficulty[p[i]:p[i+1]]) for i in range(d)))
        return best
