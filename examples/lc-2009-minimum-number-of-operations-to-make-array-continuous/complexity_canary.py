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
    def minOperations(self, nums: List[int]) -> int:
        arr=sorted(set(nums));n=len(nums);best=0
        for left in arr:
            kept=sum(left<=x<=left+n-1 for x in arr)
            best=max(best,kept)
        return n-best
