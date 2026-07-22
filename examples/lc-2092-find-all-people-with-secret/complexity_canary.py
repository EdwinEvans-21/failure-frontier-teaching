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
    def findAllPeople(self, n: int, meetings: List[List[int]], firstPerson: int) -> List[int]:
        know={0,firstPerson};by=defaultdict(list)
        for a,b,t in meetings:by[t].append((a,b))
        for t in sorted(by):
            local=set(know);changed=True
            while changed:
                changed=False
                for a,b in by[t]:
                    if a in local and b not in local:local.add(b);changed=True
                    if b in local and a not in local:local.add(a);changed=True
            participants={x for e in by[t] for x in e}
            know |= local & participants
        return sorted(know)
