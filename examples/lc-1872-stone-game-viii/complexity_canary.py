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
    def stoneGameVIII(self, stones: List[int]) -> int:
        def game(state):
            if len(state)==1:return 0
            best=-inf
            running=0
            for x in range(2,len(state)+1):
                running+=state[x-1] if x>2 else sum(state[:2])
                merged=sum(state[:x])
                best=max(best,merged-game((merged,)+state[x:]))
            return best
        return game(tuple(stones))
