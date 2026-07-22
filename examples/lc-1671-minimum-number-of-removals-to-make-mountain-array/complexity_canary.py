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
    def minimumMountainRemovals(self, nums: List[int]) -> int:
        n=len(nums); best=0
        for mask in range(1<<n):
            if mask.bit_count()<=best: continue
            a=[nums[i] for i in range(n) if mask>>i&1]
            for peak in range(1,len(a)-1):
                if all(a[i]<a[i+1] for i in range(peak)) and all(a[i]>a[i+1] for i in range(peak,len(a)-1)):
                    best=len(a); break
        return n-best
