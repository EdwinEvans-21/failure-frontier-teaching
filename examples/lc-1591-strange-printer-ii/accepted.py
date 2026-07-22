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
    def isPrintable(self, targetGrid: List[List[int]]) -> bool:
        m,n=len(targetGrid),len(targetGrid[0]); colors=set(map(int,sum(targetGrid,[])))
        box={c:[m,n,-1,-1] for c in colors}
        for i in range(m):
            for j,c in enumerate(targetGrid[i]):
                b=box[c];b[0]=min(b[0],i);b[1]=min(b[1],j);b[2]=max(b[2],i);b[3]=max(b[3],j)
        dep={c:set() for c in colors}
        for c,(a,b,x,y) in box.items():
            for i in range(a,x+1):
                for j in range(b,y+1):
                    if targetGrid[i][j]!=c:dep[c].add(targetGrid[i][j])
        state={}
        def dfs(c):
            if state.get(c)==1:return False
            if state.get(c)==2:return True
            state[c]=1
            if any(not dfs(d) for d in dep[c]):return False
            state[c]=2;return True
        return all(dfs(c) for c in colors)
