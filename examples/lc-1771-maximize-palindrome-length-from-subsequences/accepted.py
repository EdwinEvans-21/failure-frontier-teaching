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
    def longestPalindrome(self, word1: str, word2: str) -> int:
        s=word1+word2;n=len(s);split=len(word1);dp=[[0]*n for _ in range(n)];ans=0
        for i in range(n):dp[i][i]=1
        for length in range(2,n+1):
            for i in range(n-length+1):
                j=i+length-1
                if s[i]==s[j]:
                    dp[i][j]=(dp[i+1][j-1] if length>2 else 0)+2
                    if i<split<=j:ans=max(ans,dp[i][j])
                else:dp[i][j]=max(dp[i+1][j],dp[i][j-1])
        return ans
