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
    def palindromePartition(self, s: str, k: int) -> int:
        n=len(s); cost=[[0]*n for _ in range(n)]
        for d in range(1,n):
            for i in range(n-d):
                j=i+d; cost[i][j]=(cost[i+1][j-1] if d>1 else 0)+(s[i]!=s[j])
        dp=[[inf]*(k+1) for _ in range(n+1)]; dp[0][0]=0
        for i in range(1,n+1):
            for p in range(1,min(k,i)+1):
                dp[i][p]=min(dp[j][p-1]+cost[j][i-1] for j in range(p-1,i))
        return dp[n][k]
