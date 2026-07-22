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
    def maxSatisfaction(self, satisfaction: List[int]) -> int:
        ans=run=0
        for x in sorted(satisfaction,reverse=True):
            if run+x<=0:break
            run+=x; ans+=run
        return ans
