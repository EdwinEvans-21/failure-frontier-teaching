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
    def minWastedSpace(self, packages: List[int], boxes: List[List[int]]) -> int:
        best=inf
        for supplier in boxes:
            waste=0;ok=True
            for p in packages:
                fitting=[b for b in supplier if b>=p]
                if not fitting:ok=False;break
                waste+=min(fitting)-p
            if ok:best=min(best,waste)
        return -1 if best==inf else best%MOD
