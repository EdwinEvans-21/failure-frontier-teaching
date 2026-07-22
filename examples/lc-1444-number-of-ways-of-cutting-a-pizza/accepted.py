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
    def ways(self, pizza: List[str], k: int) -> int:
        m,n=len(pizza),len(pizza[0]); pre=[[0]*(n+1) for _ in range(m+1)]
        for i in range(m-1,-1,-1):
            for j in range(n-1,-1,-1):pre[i][j]=pre[i+1][j]+pre[i][j+1]-pre[i+1][j+1]+(pizza[i][j]=='A')
        dp=[[1 if pre[i][j] else 0 for j in range(n)] for i in range(m)]
        for _ in range(1,k):
            nd=[[0]*n for _ in range(m)]
            for i in range(m):
                for j in range(n):
                    for x in range(i+1,m):
                        if pre[i][j]-pre[x][j]>0:nd[i][j]=(nd[i][j]+dp[x][j])%MOD
                    for y in range(j+1,n):
                        if pre[i][j]-pre[i][y]>0:nd[i][j]=(nd[i][j]+dp[i][y])%MOD
            dp=nd
        return dp[0][0]
