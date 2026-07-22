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
    def maxHeight(self, cuboids: List[List[int]]) -> int:
        c=sorted(sorted(x) for x in cuboids);n=len(c);dp=[x[2] for x in c]
        for i in range(n):
            for j in range(i):
                if all(c[j][d]<=c[i][d] for d in range(3)):dp[i]=max(dp[i],dp[j]+c[i][2])
        return max(dp)
