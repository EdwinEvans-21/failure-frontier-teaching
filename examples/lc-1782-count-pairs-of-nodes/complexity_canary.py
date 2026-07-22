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
    def countPairs(self, n: int, edges: List[List[int]], queries: List[int]) -> List[int]:
        degree=[0]*(n+1); shared=Counter()
        for a,b in edges:
            degree[a]+=1;degree[b]+=1
            if a>b:a,b=b,a
            shared[a,b]+=1
        out=[]
        for q in queries:
            total=0
            for a in range(1,n+1):
                for b in range(a+1,n+1):
                    total += degree[a]+degree[b]-shared[a,b] > q
            out.append(total)
        return out
