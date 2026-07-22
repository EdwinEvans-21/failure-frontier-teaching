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
    def kthSmallest(self, mat: List[List[int]], k: int) -> int:
        sums=[0]
        for row in mat:
            cand=[]
            for a in sums:
                for b in row:
                    cand.append(a+b)
            sums=sorted(cand)[:k]
        return sums[k-1]
