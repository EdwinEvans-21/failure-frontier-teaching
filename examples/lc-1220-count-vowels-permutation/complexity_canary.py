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
    def countVowelPermutation(self, n: int) -> int:
        nxt = {'a':'e','e':'ai','i':'aeou','o':'iu','u':'a'}
        def dfs(ch: str, length: int) -> int:
            if length == n:
                return 1
            return sum(dfs(other, length + 1) for other in nxt[ch])
        return sum(dfs(ch, 1) for ch in 'aeiou') % MOD
