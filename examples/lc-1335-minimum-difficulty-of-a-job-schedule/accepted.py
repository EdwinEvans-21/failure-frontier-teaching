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
    def minDifficulty(self, jobDifficulty: List[int], d: int) -> int:
        n=len(jobDifficulty)
        if n<d:return -1
        dp=[inf]*n; mx=0
        for i,x in enumerate(jobDifficulty):mx=max(mx,x);dp[i]=mx
        for day in range(2,d+1):
            nd=[inf]*n
            for i in range(day-1,n):
                mx=0
                for j in range(i,day-2,-1):mx=max(mx,jobDifficulty[j]);nd[i]=min(nd[i],dp[j-1]+mx)
            dp=nd
        return dp[-1]
