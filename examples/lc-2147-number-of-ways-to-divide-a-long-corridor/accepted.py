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
    def numberOfWays(self, corridor: str) -> int:
        seats=[i for i,c in enumerate(corridor) if c=='S']
        if len(seats)==0 or len(seats)%2:return 0
        ans=1
        for i in range(2,len(seats),2):ans=ans*(seats[i]-seats[i-1])%MOD
        return ans
