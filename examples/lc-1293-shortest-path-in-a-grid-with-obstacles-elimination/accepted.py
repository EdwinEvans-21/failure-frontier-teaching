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
    def shortestPath(self, grid: List[List[int]], k: int) -> int:
        m,n=len(grid),len(grid[0])
        if k>=m+n-3:return m+n-2
        q=deque([(0,0,k,0)]); best={(0,0):k}
        while q:
            i,j,r,d=q.popleft()
            if i==m-1 and j==n-1:return d
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                x,y=i+di,j+dj
                if 0<=x<m and 0<=y<n:
                    nr=r-grid[x][y]
                    if nr>=0 and nr>best.get((x,y),-1):best[x,y]=nr;q.append((x,y,nr,d+1))
        return -1
