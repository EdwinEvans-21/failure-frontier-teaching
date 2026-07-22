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
    def numberOfCombinations(self, num: str) -> int:
        if num[0]=='0':return 0
        def dfs(i,previous):
            if i==len(num):return 1
            if num[i]=='0':return 0
            total=0
            for j in range(i+1,len(num)+1):
                cur=num[i:j]
                if len(cur)>len(previous) or len(cur)==len(previous) and cur>=previous:
                    total+=dfs(j,cur)
            return total%MOD
        return dfs(0,'')
