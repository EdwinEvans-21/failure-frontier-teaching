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
    def getMaxGridHappiness(self, m: int, n: int, introvertsCount: int, extrovertsCount: int) -> int:
        cells=m*n; best=0
        for state in product((0,1,2), repeat=cells):
            if state.count(1)>introvertsCount or state.count(2)>extrovertsCount: continue
            score=sum(120 if x==1 else 40 if x==2 else 0 for x in state)
            for p,x in enumerate(state):
                if not x: continue
                r,c=divmod(p,n)
                for q in ((r-1)*n+c if r else -1, r*n+c-1 if c else -1):
                    if q>=0 and state[q]:
                        score += (-30 if x==1 else 20) + (-30 if state[q]==1 else 20)
            best=max(best,score)
        return best
