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
    def maxNumEdgesToRemove(self, n: int, edges: List[List[int]]) -> int:
        class DSU:
            def __init__(self,n):self.p=list(range(n));self.c=n
            def find(self,x):
                while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=self.p[x]
                return x
            def union(self,a,b):
                a=self.find(a);b=self.find(b)
                if a==b:return False
                self.p[b]=a;self.c-=1;return True
        A=DSU(n);B=DSU(n);used=0
        for t,u,v in edges:
            if t==3:
                x=A.union(u-1,v-1);y=B.union(u-1,v-1);used+=x or y
        for t,u,v in edges:
            if t==1:used+=A.union(u-1,v-1)
            elif t==2:used+=B.union(u-1,v-1)
        return len(edges)-used if A.c==B.c==1 else -1
