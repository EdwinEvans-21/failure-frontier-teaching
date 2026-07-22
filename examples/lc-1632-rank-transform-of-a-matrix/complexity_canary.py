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
    def matrixRankTransform(self, matrix: List[List[int]]) -> List[List[int]]:
        rows,cols=len(matrix),len(matrix[0]); groups=defaultdict(list)
        for r in range(rows):
            for c in range(cols): groups[matrix[r][c]].append((r,c))
        answer=[[0]*cols for _ in range(rows)]; processed=[]
        for value in sorted(groups):
            cells=groups[value]; remaining=set(range(len(cells))); components=[]
            while remaining:
                comp={remaining.pop()}; changed=True
                while changed:
                    changed=False
                    for j in list(remaining):
                        if any(cells[j][0]==cells[i][0] or cells[j][1]==cells[i][1] for i in comp):
                            remaining.remove(j); comp.add(j); changed=True
                components.append(comp)
            updates=[]
            for comp in components:
                base=0
                for idx in comp:
                    r,c=cells[idx]
                    for pr,pc in processed:
                        if pr==r or pc==c: base=max(base,answer[pr][pc])
                rank=base+1
                for idx in comp: updates.append((*cells[idx],rank))
            for r,c,rank in updates: answer[r][c]=rank; processed.append((r,c))
        return answer
