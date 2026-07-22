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
    def maxTotalFruits(self, fruits: List[List[int]], startPos: int, k: int) -> int:
        pos=[p for p,_ in fruits];pre=[0]
        for _,a in fruits:pre.append(pre[-1]+a)
        ans=0;l=0
        for r,p in enumerate(pos):
            while l<=r:
                left=pos[l];dist=min(abs(startPos-left)*2+abs(p-startPos),abs(startPos-left)+abs(p-startPos)*2)
                if left<=startPos<=p:pass
                elif p<startPos:dist=startPos-left
                elif left>startPos:dist=p-startPos
                if dist<=k:break
                l+=1
            if l<=r:ans=max(ans,pre[r+1]-pre[l])
        return ans
