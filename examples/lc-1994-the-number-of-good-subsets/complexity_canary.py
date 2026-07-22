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
    def numberOfGoodSubsets(self, nums: List[int]) -> int:
        answer=0;n=len(nums)
        for mask in range(1,1<<n):
            product_value=1
            for i in range(n):
                if mask>>i&1:product_value*=nums[i]
            if product_value==1:continue
            x=product_value;p=2;valid=True
            while p*p<=x:
                count=0
                while x%p==0:x//=p;count+=1
                if count>1:valid=False;break
                p+=1
            answer+=valid
        return answer%MOD
