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
    def numberOfUniqueGoodSubsequences(self, binary: str) -> int:
        end0=end1=0;has0=0
        for c in binary:
            if c=='1':end1=(end0+end1+1)%MOD
            else:end0=(end0+end1)%MOD;has0=1
        return (end0+end1+has0)%MOD
