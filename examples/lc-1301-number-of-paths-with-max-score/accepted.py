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
    def pathsWithMaxScore(self, board: List[str]) -> List[int]:
        n=len(board); score=[[-1]*n for _ in range(n)]; ways=[[0]*n for _ in range(n)]
        score[n-1][n-1]=0; ways[n-1][n-1]=1
        for i in range(n-1,-1,-1):
            for j in range(n-1,-1,-1):
                if board[i][j]=='X' or (i==n-1 and j==n-1):continue
                candidates=[]
                for x,y in ((i+1,j),(i,j+1),(i+1,j+1)):
                    if x<n and y<n and score[x][y]>=0:candidates.append((score[x][y],ways[x][y]))
                if not candidates:continue
                mx=max(x for x,_ in candidates); add=0 if board[i][j] in 'SE' else int(board[i][j])
                score[i][j]=mx+add; ways[i][j]=sum(w for x,w in candidates if x==mx)%MOD
        return [max(score[0][0],0),ways[0][0]] if ways[0][0] else [0,0]
