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
    def waysToBuildRooms(self, prevRoom: List[int]) -> int:
        n=len(prevRoom);dp=[0]*(1<<n);dp[1]=1
        for mask in range(1<<n):
            if not dp[mask]:continue
            for room in range(1,n):
                if not mask>>room&1 and mask>>prevRoom[room]&1:
                    dp[mask|1<<room]=(dp[mask|1<<room]+dp[mask])%MOD
        return dp[-1]
