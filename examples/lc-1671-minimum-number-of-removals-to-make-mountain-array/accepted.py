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
    def minimumMountainRemovals(self, nums: List[int]) -> int:
        n=len(nums);inc=[0]*n;tails=[]
        for i,x in enumerate(nums):
            j=bisect_left(tails,x)
            if j==len(tails):tails.append(x)
            else:tails[j]=x
            inc[i]=j+1
        dec=[0]*n;tails=[]
        for i in range(n-1,-1,-1):
            x=nums[i];j=bisect_left(tails,x)
            if j==len(tails):tails.append(x)
            else:tails[j]=x
            dec[i]=j+1
        return n-max((inc[i]+dec[i]-1 for i in range(n) if inc[i]>1 and dec[i]>1),default=0)
