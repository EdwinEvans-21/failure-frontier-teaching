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
    def minimumDeviation(self, nums: List[int]) -> int:
        choices=[]
        for x in nums:
            if x%2: vals=[x,2*x]
            else:
                vals=[]
                while True:
                    vals.append(x)
                    if x%2: break
                    x//=2
            choices.append(sorted(set(vals)))
        return min(max(v)-min(v) for v in product(*choices))
