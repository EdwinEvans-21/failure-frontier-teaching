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
    def minSpaceWastedKResizing(self, nums: List[int], k: int) -> int:
        n=len(nums);best=inf
        for cuts in combinations(range(1,n),k):
            p=(0,)+cuts+(n,)
            waste=0
            for i in range(k+1):
                seg=nums[p[i]:p[i+1]];waste+=max(seg)*len(seg)-sum(seg)
            best=min(best,waste)
        return best
