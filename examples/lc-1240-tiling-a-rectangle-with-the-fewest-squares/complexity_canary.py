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
    def tilingRectangle(self, n: int, m: int) -> int:
        filled = [[False]*m for _ in range(n)]
        best = n*m
        def dfs(used: int) -> None:
            nonlocal best
            if used >= best:
                return
            cell = None
            for i in range(n):
                for j in range(m):
                    if not filled[i][j]:
                        cell=(i,j); break
                if cell: break
            if cell is None:
                best=used; return
            i,j=cell
            maximum=min(n-i,m-j)
            for size in range(1, maximum+1):
                if any(filled[x][y] for x in range(i,i+size) for y in range(j,j+size)):
                    break
                for x in range(i,i+size):
                    for y in range(j,j+size): filled[x][y]=True
                dfs(used+1)
                for x in range(i,i+size):
                    for y in range(j,j+size): filled[x][y]=False
        dfs(0)
        return best
