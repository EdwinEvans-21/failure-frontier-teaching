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
    def numWays(self, words: List[str], target: str) -> int:
        columns=len(words[0]); t=len(target); dp=[0]*(t+1);dp[0]=1
        for col in range(columns):
            nd=dp[:]
            for j in range(t):
                count=sum(word[col]==target[j] for word in words)
                nd[j+1]=(nd[j+1]+dp[j]*count)%MOD
            dp=nd
        return dp[t]
