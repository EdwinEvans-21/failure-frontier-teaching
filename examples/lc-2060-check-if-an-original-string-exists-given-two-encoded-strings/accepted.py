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
    def possiblyEquals(self, s1: str, s2: str) -> bool:
        @lru_cache(None)
        def dfs(i,j,diff):
            if i==len(s1) and j==len(s2):return diff==0
            if i<len(s1) and s1[i].isdigit():
                x=0
                for p in range(i,min(len(s1),i+3)):
                    if not s1[p].isdigit():break
                    x=x*10+int(s1[p])
                    if dfs(p+1,j,diff+x):return True
            if j<len(s2) and s2[j].isdigit():
                x=0
                for p in range(j,min(len(s2),j+3)):
                    if not s2[p].isdigit():break
                    x=x*10+int(s2[p])
                    if dfs(i,p+1,diff-x):return True
            if diff>0 and j<len(s2) and s2[j].isalpha() and dfs(i,j+1,diff-1):return True
            if diff<0 and i<len(s1) and s1[i].isalpha() and dfs(i+1,j,diff+1):return True
            if diff==0 and i<len(s1) and j<len(s2) and s1[i].isalpha() and s2[j].isalpha() and s1[i]==s2[j] and dfs(i+1,j+1,0):return True
            return False
        return dfs(0,0,0)
