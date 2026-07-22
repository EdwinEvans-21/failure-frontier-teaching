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
    def maximumInvitations(self, favorite: List[int]) -> int:
        n=len(favorite);ind=[0]*n
        for v in favorite:ind[v]+=1
        q=deque(i for i in range(n) if ind[i]==0);depth=[1]*n
        while q:
            u=q.popleft();v=favorite[u];depth[v]=max(depth[v],depth[u]+1);ind[v]-=1
            if ind[v]==0:q.append(v)
        longest=0;pairs=0
        for i in range(n):
            if ind[i]:
                cycle=[];u=i
                while ind[u]:ind[u]=0;cycle.append(u);u=favorite[u]
                if len(cycle)==2:pairs+=depth[cycle[0]]+depth[cycle[1]]
                else:longest=max(longest,len(cycle))
        return max(longest,pairs)
