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
    def makeArrayIncreasing(self, arr1: List[int], arr2: List[int]) -> int:
        values = sorted(set(arr2))
        def dfs(i: int, previous: int) -> int:
            if i == len(arr1):
                return 0
            answer = inf
            if arr1[i] > previous:
                answer = dfs(i + 1, arr1[i])
            for value in values:
                if value > previous:
                    answer = min(answer, 1 + dfs(i + 1, value))
                    break
            return answer
        result = dfs(0, -10**30)
        return -1 if result == inf else result
