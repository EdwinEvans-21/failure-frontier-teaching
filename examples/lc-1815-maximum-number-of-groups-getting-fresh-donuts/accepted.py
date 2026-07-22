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
    def maxHappyGroups(self, batchSize: int, groups: List[int]) -> int:
        cnt=[0]*batchSize
        for g in groups:cnt[g%batchSize]+=1
        base=cnt[0];cnt[0]=0
        @lru_cache(None)
        def f(state,rem):
            arr=list(state);best=0
            for r,c in enumerate(arr):
                if c:
                    arr[r]-=1
                    best=max(best,(rem==0)+f(tuple(arr),(rem+r)%batchSize))
                    arr[r]+=1
            return best
        return base+f(tuple(cnt),0)
