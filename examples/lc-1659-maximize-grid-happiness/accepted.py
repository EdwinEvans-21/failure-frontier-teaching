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
    def getMaxGridHappiness(self, m: int, n: int, introvertsCount: int, extrovertsCount: int) -> int:
        if m<n:m,n=n,m
        pow3=3**n; states=[]
        for mask in range(pow3):
            x=mask;arr=[];ic=ec=base=0
            for _ in range(n):
                t=x%3;x//=3;arr.append(t)
                if t==1:ic+=1;base+=120
                elif t==2:ec+=1;base+=40
            for j in range(1,n):
                a,b=arr[j-1],arr[j]
                if a and b:base+=(-60 if a==b==1 else 40 if a==b==2 else -10)
            states.append((arr,ic,ec,base))
        cross=[[0]*pow3 for _ in range(pow3)]
        for a in range(pow3):
            for b in range(pow3):
                v=0
                for x,y in zip(states[a][0],states[b][0]):
                    if x and y:v+=(-60 if x==y==1 else 40 if x==y==2 else -10)
                cross[a][b]=v
        dp={(0,0,0):0}
        for _ in range(m):
            nd={}
            for (prev,ic,ec),v in dp.items():
                for s,(arr,di,de,base) in enumerate(states):
                    if ic+di<=introvertsCount and ec+de<=extrovertsCount:
                        key=(s,ic+di,ec+de);nd[key]=max(nd.get(key,-1),v+base+cross[prev][s])
            dp=nd
        return max(dp.values(),default=0)
