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
    def minDays(self, n: int) -> int:
        @lru_cache(None)
        def f(x):
            if x<=1:return x
            return 1+min(x%2+f(x//2),x%3+f(x//3))
        return f(n)
