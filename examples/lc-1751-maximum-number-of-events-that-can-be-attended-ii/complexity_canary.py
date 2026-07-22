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
    def maxValue(self, events: List[List[int]], k: int) -> int:
        events=sorted(events)
        def dfs(i,last_end,left):
            if i==len(events) or left==0:return 0
            best=dfs(i+1,last_end,left)
            if events[i][0]>last_end: best=max(best,events[i][2]+dfs(i+1,events[i][1],left-1))
            return best
        return dfs(0,-1,k)
