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
    def maxSatisfaction(self, satisfaction: List[int]) -> int:
        best=0;n=len(satisfaction)
        for mask in range(1<<n):
            chosen=sorted(satisfaction[i] for i in range(n) if mask>>i&1)
            best=max(best,sum((i+1)*x for i,x in enumerate(chosen)))
        return best
