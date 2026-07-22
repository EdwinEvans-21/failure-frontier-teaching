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
    def minFlips(self, mat: List[List[int]]) -> int:
        m,n=len(mat),len(mat[0]); cells=m*n
        start=0; masks=[]
        for i in range(m):
            for j in range(n): start |= mat[i][j] << (i*n+j)
        for i in range(m):
            for j in range(n):
                z=0
                for di,dj in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                    x,y=i+di,j+dj
                    if 0<=x<m and 0<=y<n: z ^= 1 << (x*n+y)
                masks.append(z)
        def search(state, depth):
            if state==0: return True
            if depth==0: return False
            return any(search(state^mask,depth-1) for mask in masks)
        for depth in range(cells+1):
            if search(start,depth): return depth
        return -1
