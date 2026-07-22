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
    def numRollsToTarget(self, n: int, k: int, target: int) -> int:
        def dfs(left: int, total: int) -> int:
            if left == 0:
                return int(total == 0)
            if total < left or total > left * k:
                return 0
            return sum(dfs(left - 1, total - face) for face in range(1, k + 1)) % MOD
        return dfs(n, target)
