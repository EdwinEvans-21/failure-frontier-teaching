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
    def numWays(self, words: List[str], target: str) -> int:
        L=len(words[0]); cnt=[[0]*26 for _ in range(L)]
        for w in words:
            for i,c in enumerate(w):cnt[i][ord(c)-97]+=1
        dp=[0]*(len(target)+1);dp[0]=1
        for i in range(L):
            for j in range(min(i+1,len(target)),0,-1):dp[j]=(dp[j]+dp[j-1]*cnt[i][ord(target[j-1])-97])%MOD
        return dp[-1]
