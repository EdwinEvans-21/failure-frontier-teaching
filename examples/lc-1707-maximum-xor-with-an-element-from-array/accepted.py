from __future__ import annotations
from typing import List
class Solution:
    def maximizeXor(self, nums: List[int], queries: List[List[int]]) -> List[int]:
        nums.sort(); ordered=sorted((m,x,i) for i,(x,m) in enumerate(queries)); ans=[-1]*len(queries)
        left=[-1]; right=[-1]
        def add(v):
            node=0
            for b in range(30,-1,-1):
                bit=(v>>b)&1; arr=right if bit else left; nxt=arr[node]
                if nxt<0:
                    nxt=len(left); arr[node]=nxt; left.append(-1); right.append(-1)
                node=nxt
        j=0
        for m,x,idx in ordered:
            while j<len(nums) and nums[j]<=m: add(nums[j]); j+=1
            if j==0: continue
            node=0; val=0
            for b in range(30,-1,-1):
                bit=(x>>b)&1; preferred=left[node] if bit else right[node]
                if preferred>=0: val|=1<<b; node=preferred
                else: node=right[node] if bit else left[node]
            ans[idx]=val
        return ans
