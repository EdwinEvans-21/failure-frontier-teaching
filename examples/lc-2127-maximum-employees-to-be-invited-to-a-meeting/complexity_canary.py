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
    def maximumInvitations(self, favorite: List[int]) -> int:
        n=len(favorite);reverse=[[] for _ in range(n)]
        for i,v in enumerate(favorite):reverse[v].append(i)
        longest=0
        for start in range(n):
            pos={};u=start;step=0
            while u not in pos:
                pos[u]=step;step+=1;u=favorite[u]
            longest=max(longest,step-pos[u])
        def chain(root,blocked):
            best=1
            stack=[(root,1,{root,blocked})]
            while stack:
                u,d,used=stack.pop();best=max(best,d)
                for v in reverse[u]:
                    if v not in used:stack.append((v,d+1,used|{v}))
            return best
        pairs=0
        for a in range(n):
            b=favorite[a]
            if a<b and favorite[b]==a:pairs+=chain(a,b)+chain(b,a)
        return max(longest,pairs)
