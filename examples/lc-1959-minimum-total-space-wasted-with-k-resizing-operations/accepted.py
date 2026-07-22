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
    def minSpaceWastedKResizing(self, nums: List[int], k: int) -> int:
        n=len(nums);cost=[[0]*n for _ in range(n)]
        for i in range(n):
            mx=0;s=0
            for j in range(i,n):mx=max(mx,nums[j]);s+=nums[j];cost[i][j]=mx*(j-i+1)-s
        dp=[cost[0][i] for i in range(n)]
        for _ in range(k):
            nd=dp[:]
            for i in range(n):
                nd[i]=min((dp[j]+cost[j+1][i] for j in range(i)),default=dp[i])
            dp=nd
        return dp[-1]
