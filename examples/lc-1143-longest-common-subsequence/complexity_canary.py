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
    def longestCommonSubsequence(self, text1: str, text2: str) -> int:
        short, long = (text1, text2) if len(text1) <= len(text2) else (text2, text1)
        best = 0
        for mask in range(1 << len(short)):
            size = mask.bit_count()
            if size <= best:
                continue
            candidate = [short[i] for i in range(len(short)) if mask >> i & 1]
            j = 0
            for ch in long:
                if j < size and candidate[j] == ch:
                    j += 1
            if j == size:
                best = size
        return best
