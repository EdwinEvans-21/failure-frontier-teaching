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
    def numberOfArrays(self, s: str, k: int) -> int:
        n=len(s); dp=[0]*(n+1);dp[n]=1; L=len(str(k))
        for i in range(n-1,-1,-1):
            if s[i]=='0':continue
            x=0
            for j in range(i,min(n,i+L)):
                x=x*10+int(s[j])
                if x>k:break
                dp[i]=(dp[i]+dp[j+1])%MOD
        return dp[0]
