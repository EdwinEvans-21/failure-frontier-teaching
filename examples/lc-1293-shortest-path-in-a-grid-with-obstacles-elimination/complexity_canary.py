from __future__ import annotations
from typing import *
from functools import lru_cache
from collections import defaultdict, deque, Counter
from itertools import combinations, permutations, product
from bisect import bisect_left, bisect_right
from heapq import heappush, heappop
from math import gcd, factorial, comb, inf, isqrt

MOD = 1_000_000_007

class Solution:
    def shortestPath(self, grid: List[List[int]], k: int) -> int:
        m,n=len(grid),len(grid[0]); target=(m-1,n-1)
        def possible(limit):
            seen={(0,0)}
            def dfs(i,j,left,steps):
                if (i,j)==target: return True
                if steps==limit: return False
                if steps+abs(target[0]-i)+abs(target[1]-j)>limit: return False
                for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                    x,y=i+di,j+dj
                    if 0<=x<m and 0<=y<n and (x,y) not in seen:
                        nl=left-grid[x][y]
                        if nl>=0:
                            seen.add((x,y))
                            if dfs(x,y,nl,steps+1): return True
                            seen.remove((x,y))
                return False
            return dfs(0,0,k,0)
        for length in range(m*n):
            if possible(length): return length
        return -1
