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
    def minWastedSpace(self, packages: List[int], boxes: List[List[int]]) -> int:
        packages=sorted(packages);pre=[0]
        for x in packages:pre.append(pre[-1]+x)
        ans=inf;n=len(packages)
        for supplier in boxes:
            supplier=sorted(supplier)
            if supplier[-1]<packages[-1]:continue
            total=0;i=0
            for b in supplier:
                j=bisect_right(packages,b,i)
                total+=b*(j-i)-(pre[j]-pre[i]);i=j
                if i==n:break
            ans=min(ans,total)
        return -1 if ans==inf else ans%MOD
