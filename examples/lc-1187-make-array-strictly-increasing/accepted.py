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
    def makeArrayIncreasing(self, arr1: List[int], arr2: List[int]) -> int:
        arr2 = sorted(set(arr2)); dp = {-10**20: 0}
        for x in arr1:
            nd = {}
            for last, cost in dp.items():
                if x > last: nd[x] = min(nd.get(x, inf), cost)
                j = bisect_right(arr2, last)
                if j < len(arr2): nd[arr2[j]] = min(nd.get(arr2[j], inf), cost + 1)
            dp = nd
            if not dp: return -1
        return min(dp.values())
