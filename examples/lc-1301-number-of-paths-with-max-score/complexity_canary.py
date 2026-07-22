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
    def pathsWithMaxScore(self, board: List[str]) -> List[int]:
        n=len(board); best=-1; ways=0
        def dfs(i,j,score):
            nonlocal best,ways
            if i<0 or j<0 or board[i][j]=='X': return
            if i==0 and j==0:
                if score>best: best,ways=score,1
                elif score==best: ways=(ways+1)%MOD
                return
            add=0 if board[i][j] in 'SE' else int(board[i][j])
            dfs(i-1,j,score+add); dfs(i,j-1,score+add); dfs(i-1,j-1,score+add)
        dfs(n-1,n-1,0)
        return [0,0] if best<0 else [best,ways%MOD]
