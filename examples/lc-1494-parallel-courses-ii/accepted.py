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
    def minNumberOfSemesters(self, n: int, relations: List[List[int]], k: int) -> int:
        pre=[0]*n
        for a,b in relations:pre[b-1]|=1<<(a-1)
        full=(1<<n)-1; dist=[-1]*(1<<n);dist[0]=0;q=deque([0])
        while q:
            mask=q.popleft()
            if mask==full:return dist[mask]
            avail=0
            for i in range(n):
                if not mask>>i&1 and pre[i]&mask==pre[i]:avail|=1<<i
            choices=[]
            if avail.bit_count()<=k:choices=[avail]
            else:
                sub=avail
                while sub:
                    if sub.bit_count()==k:choices.append(sub)
                    sub=(sub-1)&avail
            for take in choices:
                nm=mask|take
                if dist[nm]<0:dist[nm]=dist[mask]+1;q.append(nm)
        return -1
