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
    def findAllPeople(self, n: int, meetings: List[List[int]], firstPerson: int) -> List[int]:
        know={0,firstPerson};i=0;meetings=sorted(meetings,key=lambda x:x[2])
        while i<len(meetings):
            j=i;t=meetings[i][2];g=defaultdict(list);people=set()
            while j<len(meetings) and meetings[j][2]==t:
                a,b,_=meetings[j];g[a].append(b);g[b].append(a);people|={a,b};j+=1
            q=deque(p for p in people if p in know);seen=set(q)
            while q:
                u=q.popleft();know.add(u)
                for v in g[u]:
                    if v not in seen:seen.add(v);q.append(v)
            i=j
        return sorted(know)
