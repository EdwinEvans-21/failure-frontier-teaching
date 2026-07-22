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
    def minNumberOperations(self, target: List[int]) -> int:
        a=target[:]; answer=0
        while any(a):
            i=0
            while i<len(a):
                while i<len(a) and a[i]==0: i+=1
                if i==len(a): break
                answer+=1
                while i<len(a) and a[i]>0:
                    a[i]-=1; i+=1
        return answer
