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
    def isPossible(self, target: List[int]) -> bool:
        if len(target)==1:return target[0]==1
        h=[-x for x in target]; heapify(h); total=sum(target)
        while -h[0]>1:
            x=-heappop(h); rest=total-x
            if rest==1:return True
            if rest<=0 or x<=rest:return False
            y=x%rest
            if y==0:return False
            total=rest+y; heappush(h,-y)
        return True
