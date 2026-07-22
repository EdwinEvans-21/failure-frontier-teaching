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
    def minOperations(self, nums: List[int]) -> int:
        arr=sorted(set(nums));n=len(nums);best=0
        for i,x in enumerate(arr):best=max(best,bisect_right(arr,x+n-1)-i)
        return n-best
