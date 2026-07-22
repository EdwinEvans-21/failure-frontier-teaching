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
    def minimumDifference(self, nums: List[int]) -> int:
        n=len(nums)//3;best=inf;indices=range(len(nums))
        for removed in combinations(indices,n):
            gone=set(removed);left=[nums[i] for i in indices if i not in gone]
            best=min(best,sum(left[:n])-sum(left[n:]))
        return best
