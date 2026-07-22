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
    def maxValue(self, events: List[List[int]], k: int) -> int:
        events=sorted(events); starts=[e[0] for e in events]; n=len(events)
        nxt=[bisect_right(starts,e[1]) for e in events]
        dp=[0]*(n+1)
        for _ in range(k):
            nd=dp[:]
            for i in range(n-1,-1,-1):
                nd[i]=max(nd[i+1],events[i][2]+dp[nxt[i]])
            dp=nd
        return dp[0]
