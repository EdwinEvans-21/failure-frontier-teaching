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
    def minNumberOperations(self, target: List[int]) -> int:
        return target[0]+sum(max(0,b-a) for a,b in zip(target,target[1:]))
