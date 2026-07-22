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
    def makeStringSorted(self, s: str) -> int:
        count=Counter(s); answer=0
        for i,ch in enumerate(s):
            remaining=len(s)-i-1
            for smaller in sorted(c for c,v in count.items() if v and c<ch):
                count[smaller]-=1
                ways=factorial(remaining)
                for v in count.values(): ways//=factorial(v)
                answer=(answer+ways)%MOD
                count[smaller]+=1
            count[ch]-=1
        return answer
