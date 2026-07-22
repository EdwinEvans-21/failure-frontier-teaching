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
    def maxStudents(self, seats: List[List[str]]) -> int:
        m,n=len(seats),len(seats[0]); valid=[]
        for row in seats:
            avail=sum((c=='.')<<j for j,c in enumerate(row)); masks=[]
            for mask in range(1<<n):
                if mask&~avail==0 and mask&(mask<<1)==0:masks.append(mask)
            valid.append(masks)
        dp={0:0}
        for masks in valid:
            nd={}
            for mask in masks:
                for pm,v in dp.items():
                    if mask&(pm<<1)==0 and mask&(pm>>1)==0:nd[mask]=max(nd.get(mask,0),v+mask.bit_count())
            dp=nd
        return max(dp.values(),default=0)
