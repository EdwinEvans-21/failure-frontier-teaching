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
    def winnerSquareGame(self, n: int) -> bool:
        win=[False]*(n+1)
        for x in range(1,n+1):
            for move in range(1,x+1):
                r=isqrt(move)
                if r*r==move and not win[x-move]:
                    win[x]=True; break
        return win[n]
