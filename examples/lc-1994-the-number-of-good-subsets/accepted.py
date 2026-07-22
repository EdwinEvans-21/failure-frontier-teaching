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
    def numberOfGoodSubsets(self, nums: List[int]) -> int:
        primes=[2,3,5,7,11,13,17,19,23,29];cnt=Counter(nums);dp=[0]*(1<<10);dp[0]=1
        for x,c in cnt.items():
            if x==1:continue
            mask=0;valid=True;y=x
            for i,p in enumerate(primes):
                if y%(p*p)==0:valid=False;break
                if y%p==0:mask|=1<<i
            if not valid:continue
            for s in range((1<<10)-1,-1,-1):
                if s&mask==0:dp[s|mask]=(dp[s|mask]+dp[s]*c)%MOD
        return (sum(dp[1:])*pow(2,cnt[1],MOD))%MOD
