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
    def maxScore(self, nums: List[int]) -> int:
        best=0
        for order in permutations(nums):
            score=0
            for i in range(0,len(nums),2): score+=(i//2+1)*gcd(order[i],order[i+1])
            best=max(best,score)
        return best
