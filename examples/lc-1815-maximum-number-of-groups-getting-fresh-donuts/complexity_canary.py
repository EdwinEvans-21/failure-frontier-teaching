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
    def maxHappyGroups(self, batchSize: int, groups: List[int]) -> int:
        best=0
        for order in permutations(groups):
            rem=0;happy=0
            for g in order:
                if rem==0: happy+=1
                rem=(rem+g)%batchSize
            best=max(best,happy)
        return best
