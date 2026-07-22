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
    def maxTotalFruits(self, fruits: List[List[int]], startPos: int, k: int) -> int:
        best=0;n=len(fruits)
        for l in range(n):
            for r in range(l,n):
                left,right=fruits[l][0],fruits[r][0]
                if right<=startPos:steps=startPos-left
                elif left>=startPos:steps=right-startPos
                else:steps=min(2*(startPos-left)+right-startPos,startPos-left+2*(right-startPos))
                if steps<=k:best=max(best,sum(fruits[i][1] for i in range(l,r+1)))
        return best
