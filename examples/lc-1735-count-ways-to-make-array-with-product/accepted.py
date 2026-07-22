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
    def waysToFillArray(self, queries: List[List[int]]) -> List[int]:
        maxn=max(n for n,_ in queries)+20; fact=[1]*maxn;inv=[1]*maxn
        for i in range(1,maxn):fact[i]=fact[i-1]*i%MOD
        inv[-1]=pow(fact[-1],MOD-2,MOD)
        for i in range(maxn-1,0,-1):inv[i-1]=inv[i]*i%MOD
        def C(a,b):return fact[a]*inv[b]%MOD*inv[a-b]%MOD
        ans=[]
        for n,k in queries:
            x=k;res=1;p=2
            while p*p<=x:
                if x%p==0:
                    e=0
                    while x%p==0:x//=p;e+=1
                    res=res*C(n+e-1,e)%MOD
                p+=1
            if x>1:res=res*n%MOD
            ans.append(res)
        return ans
