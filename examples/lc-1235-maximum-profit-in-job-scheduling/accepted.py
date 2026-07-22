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
    def jobScheduling(self, startTime: List[int], endTime: List[int], profit: List[int]) -> int:
        jobs = sorted(zip(startTime,endTime,profit)); starts=[x[0] for x in jobs]; n=len(jobs)
        dp=[0]*(n+1)
        for i in range(n-1,-1,-1):
            j=bisect_left(starts,jobs[i][1]); dp[i]=max(dp[i+1],jobs[i][2]+dp[j])
        return dp[0]
