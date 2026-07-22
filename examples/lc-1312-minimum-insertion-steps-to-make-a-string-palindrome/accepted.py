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
    def minInsertions(self, s: str) -> int:
        n=len(s); dp=[0]*n
        for i in range(n-2,-1,-1):
            prev=0
            for j in range(i+1,n):
                old=dp[j]
                dp[j]=prev if s[i]==s[j] else min(dp[j],dp[j-1])+1
                prev=old
        return dp[-1] if n else 0
