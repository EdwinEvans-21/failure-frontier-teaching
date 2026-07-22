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
    def matrixRankTransform(self, matrix: List[List[int]]) -> List[List[int]]:
        m,n=len(matrix),len(matrix[0]); groups=defaultdict(list)
        for i in range(m):
            for j in range(n):groups[matrix[i][j]].append((i,j))
        rank=[0]*(m+n);ans=[[0]*n for _ in range(m)]
        for val in sorted(groups):
            parent={}
            def find(x):
                parent.setdefault(x,x)
                if parent[x]!=x:parent[x]=find(parent[x])
                return parent[x]
            def union(a,b):
                a=find(a);b=find(b);parent[b]=a
            for i,j in groups[val]:union(i,j+m)
            comps=defaultdict(list)
            for i,j in groups[val]:comps[find(i)].append((i,j))
            updates=[]
            for cells in comps.values():
                r=1+max(max(rank[i],rank[m+j]) for i,j in cells)
                for i,j in cells:ans[i][j]=r;updates.append((i,j,r))
            for i,j,r in updates:rank[i]=max(rank[i],r);rank[m+j]=max(rank[m+j],r)
        return ans
