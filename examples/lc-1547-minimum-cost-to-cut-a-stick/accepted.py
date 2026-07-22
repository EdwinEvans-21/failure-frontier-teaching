from __future__ import annotations
from typing import List
class Solution:
    def minCost(self, n: int, cuts: List[int]) -> int:
        a=[0]+sorted(cuts)+[n]; m=len(a); dp=[[0]*m for _ in range(m)]
        for span in range(2,m):
            for i in range(m-span):
                j=i+span
                dp[i][j]=min((dp[i][k]+dp[k][j]+a[j]-a[i] for k in range(i+1,j)), default=0)
        return dp[0][-1]
