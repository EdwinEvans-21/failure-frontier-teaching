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
    def isPossible(self, target: List[int]) -> bool:
        heap=[-x for x in target]; import heapq; heapq.heapify(heap); total=sum(target)
        while True:
            largest=-heapq.heappop(heap); rest=total-largest
            if largest==1: return True
            if rest<=0 or largest<=rest: return False
            largest-=rest
            total=rest+largest
            heapq.heappush(heap,-largest)
