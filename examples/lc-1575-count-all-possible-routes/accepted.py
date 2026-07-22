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
    def countRoutes(self, locations: List[int], start: int, finish: int, fuel: int) -> int:
        n=len(locations)
        @lru_cache(None)
        def f(i,r):
            ans=int(i==finish)
            for j in range(n):
                if j!=i:
                    c=abs(locations[i]-locations[j])
                    if c<=r:ans=(ans+f(j,r-c))%MOD
            return ans
        return f(start,fuel)
