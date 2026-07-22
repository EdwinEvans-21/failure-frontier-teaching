from __future__ import annotations
from functools import lru_cache
class Solution:
    def getLengthOfOptimalCompression(self, s: str, k: int) -> int:
        n=len(s)
        def enc(c):
            if c<=1:return 1
            if c<10:return 2
            if c<100:return 3
            return 4
        @lru_cache(None)
        def dp(i, rem):
            if rem < 0: return 10**9
            if i >= n or n-i <= rem: return 0
            freq=[0]*26; best=10**9; mx=0
            for j in range(i,n):
                x=ord(s[j])-97; freq[x]+=1; mx=max(mx,freq[x])
                deletions=(j-i+1)-mx
                if deletions<=rem:
                    best=min(best,enc(mx)+dp(j+1,rem-deletions))
            return best
        return dp(0,k)
