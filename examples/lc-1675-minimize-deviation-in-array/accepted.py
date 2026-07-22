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
    def minimumDeviation(self, nums: List[int]) -> int:
        h=[];mn=10**20
        for x in nums:
            if x%2:x*=2
            mn=min(mn,x);h.append(-x)
        heapify(h);ans=10**20
        while True:
            mx=-heappop(h);ans=min(ans,mx-mn)
            if mx%2:return ans
            mx//=2;mn=min(mn,mx);heappush(h,-mx)
