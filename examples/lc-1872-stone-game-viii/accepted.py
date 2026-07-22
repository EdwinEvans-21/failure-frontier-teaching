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
    def stoneGameVIII(self, stones: List[int]) -> int:
        pre=[];s=0
        for x in stones:s+=x;pre.append(s)
        best=pre[-1]
        for i in range(len(stones)-2,0,-1):best=max(best,pre[i]-best)
        return best
