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
    def minimumTimeRequired(self, jobs: List[int], k: int) -> int:
        jobs=sorted(jobs,reverse=True);loads=[0]*k;best=sum(jobs)
        def dfs(i):
            nonlocal best
            if i==len(jobs):best=min(best,max(loads));return
            seen=set()
            for w in range(k):
                if loads[w] in seen:continue
                seen.add(loads[w])
                if loads[w]+jobs[i]>=best:continue
                loads[w]+=jobs[i];dfs(i+1);loads[w]-=jobs[i]
                if loads[w]==0:break
        dfs(0);return best
