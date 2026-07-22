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
    def maxScore(self, nums: List[int]) -> int:
        n=len(nums);g=[[0]*n for _ in range(n)]
        for i in range(n):
            for j in range(i+1,n):g[i][j]=gcd(nums[i],nums[j])
        @lru_cache(None)
        def f(mask):
            op=mask.bit_count()//2+1
            if mask==(1<<n)-1:return 0
            i=next(i for i in range(n) if not mask>>i&1);best=0
            for j in range(i+1,n):
                if not mask>>j&1:best=max(best,op*g[i][j]+f(mask|1<<i|1<<j))
            return best
        return f(0)
