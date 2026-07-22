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
        n=len(nums)//2;total=sum(nums);best=inf
        for chosen in combinations(range(len(nums)),n):
            s=sum(nums[i] for i in chosen);best=min(best,abs(total-2*s))
        return best
