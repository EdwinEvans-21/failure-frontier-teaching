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
    def colorTheGrid(self, m: int, n: int) -> int:
        states=[]
        def gen(pos,arr):
            if pos==m:states.append(tuple(arr));return
            for c in range(3):
                if not arr or arr[-1]!=c:arr.append(c);gen(pos+1,arr);arr.pop()
        gen(0,[]);compat=[[b for b,t in enumerate(states) if all(x!=y for x,y in zip(s,t))] for s in states]
        dp=[1]*len(states)
        for _ in range(n-1):
            nd=[0]*len(states)
            for i,v in enumerate(dp):
                for j in compat[i]:nd[j]=(nd[j]+v)%MOD
            dp=nd
        return sum(dp)%MOD
