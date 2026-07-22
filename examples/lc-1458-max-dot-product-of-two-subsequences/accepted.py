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
    def maxDotProduct(self, nums1: List[int], nums2: List[int]) -> int:
        m,n=len(nums1),len(nums2); dp=[[-10**30]*(n+1) for _ in range(m+1)]
        for i in range(1,m+1):
            for j in range(1,n+1):
                p=nums1[i-1]*nums2[j-1]
                dp[i][j]=max(dp[i-1][j],dp[i][j-1],p,p+max(0,dp[i-1][j-1]))
        return dp[m][n]
