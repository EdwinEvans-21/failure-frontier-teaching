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
    def makeStringSorted(self, s: str) -> int:
        n=len(s);fact=[1]*(n+1);invfact=[1]*(n+1)
        for i in range(1,n+1):fact[i]=fact[i-1]*i%MOD
        invfact[n]=pow(fact[n],MOD-2,MOD)
        for i in range(n,0,-1):invfact[i-1]=invfact[i]*i%MOD
        cnt=Counter(s);ans=0
        for i,ch in enumerate(s):
            rem=n-i-1
            smaller=sum(v for c,v in cnt.items() if c<ch)
            if smaller:
                ways=fact[rem]*smaller%MOD
                for v in cnt.values():ways=ways*invfact[v]%MOD
                ans=(ans+ways)%MOD
            cnt[ch]-=1
            if cnt[ch]==0:del cnt[ch]
        return ans
