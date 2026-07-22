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
    def numberOfUniqueGoodSubsequences(self, binary: str) -> int:
        values=set();n=len(binary)
        for mask in range(1,1<<n):
            s=''.join(binary[i] for i in range(n) if mask>>i&1)
            if s=='0' or s[0]=='1':values.add(s)
        return len(values)%MOD
