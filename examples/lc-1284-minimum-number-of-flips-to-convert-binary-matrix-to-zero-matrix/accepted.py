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
    def minFlips(self, mat: List[List[int]]) -> int:
        m,n=len(mat),len(mat[0]); start=0
        for i in range(m):
            for j in range(n): start|=mat[i][j]<<(i*n+j)
        masks=[]
        for i in range(m):
            for j in range(n):
                z=0
                for di,dj in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                    x,y=i+di,j+dj
                    if 0<=x<m and 0<=y<n:z^=1<<(x*n+y)
                masks.append(z)
        q=deque([(start,0)]); seen={start}
        while q:
            x,d=q.popleft()
            if x==0:return d
            for z in masks:
                y=x^z
                if y not in seen:seen.add(y);q.append((y,d+1))
        return -1
