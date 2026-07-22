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
    def jobScheduling(self, startTime: List[int], endTime: List[int], profit: List[int]) -> int:
        jobs = list(zip(startTime, endTime, profit))
        best = 0
        for mask in range(1 << len(jobs)):
            chosen = sorted((jobs[i] for i in range(len(jobs)) if mask >> i & 1), key=lambda x:x[0])
            if all(chosen[i-1][1] <= chosen[i][0] for i in range(1, len(chosen))):
                best = max(best, sum(x[2] for x in chosen))
        return best
