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
    def minimumDifference(self, nums: List[int]) -> int:
        n=len(nums)//3;left=[0]*len(nums);h=[];s=0
        for i,x in enumerate(nums[:2*n]):
            heappush(h,-x);s+=x
            if len(h)>n:s+=heappop(h)
            if len(h)==n:left[i]=s
        right=[0]*len(nums);h=[];s=0
        for i in range(3*n-1,n-1,-1):
            x=nums[i];heappush(h,x);s+=x
            if len(h)>n:s-=heappop(h)
            if len(h)==n:right[i]=s
        return min(left[i]-right[i+1] for i in range(n-1,2*n))
