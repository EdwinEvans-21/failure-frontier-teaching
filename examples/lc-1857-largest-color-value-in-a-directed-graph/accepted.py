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
    def largestPathValue(self, colors: str, edges: List[List[int]]) -> int:
        n=len(colors);g=[[] for _ in range(n)];ind=[0]*n
        for u,v in edges:g[u].append(v);ind[v]+=1
        q=deque(i for i in range(n) if ind[i]==0);dp=[[0]*26 for _ in range(n)];seen=0;ans=0
        while q:
            u=q.popleft();seen+=1;c=ord(colors[u])-97;dp[u][c]+=1;ans=max(ans,dp[u][c])
            for v in g[u]:
                for j in range(26):dp[v][j]=max(dp[v][j],dp[u][j])
                ind[v]-=1
                if ind[v]==0:q.append(v)
        return ans if seen==n else -1
