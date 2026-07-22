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
    def minimumIncompatibility(self, nums: List[int], k: int) -> int:
        n=len(nums);size=n//k
        if max(Counter(nums).values())>k:return -1
        val={}
        for mask in range(1<<n):
            if mask.bit_count()!=size:continue
            arr=[nums[i] for i in range(n) if mask>>i&1]
            if len(set(arr))==size:val[mask]=max(arr)-min(arr)
        dp=[inf]*(1<<n);dp[0]=0
        for mask in range(1<<n):
            if dp[mask]==inf:continue
            first=next((i for i in range(n) if not mask>>i&1),n)
            for sub,c in val.items():
                if sub>>first&1 and not sub&mask:dp[mask|sub]=min(dp[mask|sub],dp[mask]+c)
        return dp[-1]
