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
    def minInsertions(self, s: str) -> int:
        best=0
        for mask in range(1<<len(s)):
            if mask.bit_count()<=best: continue
            t=''.join(s[i] for i in range(len(s)) if mask>>i&1)
            if t==t[::-1]: best=len(t)
        return len(s)-best
