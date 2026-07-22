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
    def countPairs(self, n: int, edges: List[List[int]], queries: List[int]) -> List[int]:
        deg=[0]*(n+1);mult=Counter()
        for u,v in edges:
            deg[u]+=1;deg[v]+=1
            if u>v:u,v=v,u
            mult[u,v]+=1
        arr=sorted(deg[1:]);ans=[]
        for q in queries:
            l=0;r=n-1;cnt=0
            while l<r:
                if arr[l]+arr[r]>q:cnt+=r-l;r-=1
                else:l+=1
            for (u,v),c in mult.items():
                if deg[u]+deg[v]>q and deg[u]+deg[v]-c<=q:cnt-=1
            ans.append(cnt)
        return ans
