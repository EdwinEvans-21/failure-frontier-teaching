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
    def minimumIncompatibility(self, nums: List[int], k: int) -> int:
        if max(Counter(nums).values())>k: return -1
        size=len(nums)//k; used=[False]*len(nums); best=inf
        def dfs(groups_left,total):
            nonlocal best
            if groups_left==0: best=min(best,total); return
            if total>=best:return
            first=next(i for i,x in enumerate(used) if not x)
            used[first]=True
            rest=[i for i,x in enumerate(used) if not x]
            for extra in combinations(rest,size-1):
                idx=(first,)+extra; vals=[nums[i] for i in idx]
                if len(set(vals))<size: continue
                for i in extra: used[i]=True
                dfs(groups_left-1,total+max(vals)-min(vals))
                for i in extra: used[i]=False
            used[first]=False
        dfs(k,0); return best
