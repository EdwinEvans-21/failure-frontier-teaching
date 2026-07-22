from __future__ import annotations
from typing import *
from collections import deque

class Solution:
    def maxNumEdgesToRemove(self, n: int, edges: List[List[int]]) -> int:
        alice=[[] for _ in range(n)]
        bob=[[] for _ in range(n)]
        used=0
        def connected(graph,a,b):
            if a==b:return True
            q=deque([a]);seen={a}
            while q:
                u=q.popleft()
                for v in graph[u]:
                    if v==b:return True
                    if v not in seen:seen.add(v);q.append(v)
            return False
        for typ,u,v in edges:
            if typ!=3:continue
            u-=1;v-=1
            if not connected(alice,u,v):
                alice[u].append(v);alice[v].append(u)
                bob[u].append(v);bob[v].append(u)
                used+=1
        for typ,u,v in edges:
            u-=1;v-=1
            if typ==1 and not connected(alice,u,v):
                alice[u].append(v);alice[v].append(u);used+=1
            elif typ==2 and not connected(bob,u,v):
                bob[u].append(v);bob[v].append(u);used+=1
        def all_connected(graph):
            q=deque([0]);seen={0}
            while q:
                u=q.popleft()
                for v in graph[u]:
                    if v not in seen:seen.add(v);q.append(v)
            return len(seen)==n
        return len(edges)-used if all_connected(alice) and all_connected(bob) else -1
