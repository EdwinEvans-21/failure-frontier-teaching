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
    def palindromePartition(self, s: str, k: int) -> int:
        def cost(a,b):
            return sum(s[a+i] != s[b-1-i] for i in range((b-a)//2))
        best=inf
        for cuts in combinations(range(1,len(s)),k-1):
            points=(0,)+cuts+(len(s),)
            best=min(best,sum(cost(points[i],points[i+1]) for i in range(k)))
        return best
