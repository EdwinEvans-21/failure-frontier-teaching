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
    def maximumRequests(self, n: int, requests: List[List[int]]) -> int:
        ans=0;m=len(requests)
        for mask in range(1<<m):
            if mask.bit_count()<=ans:continue
            bal=[0]*n
            for i,(a,b) in enumerate(requests):
                if mask>>i&1:bal[a]-=1;bal[b]+=1
            if not any(bal):ans=mask.bit_count()
        return ans
