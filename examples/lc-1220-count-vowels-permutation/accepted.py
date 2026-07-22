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
    def countVowelPermutation(self, n: int) -> int:
        a=e=i=o=u=1
        for _ in range(n-1):
            a,e,i,o,u = (e+i+u)%MOD, (a+i)%MOD, (e+o)%MOD, i%MOD, (i+o)%MOD
        return (a+e+i+o+u)%MOD
