from __future__ import annotations
from array import array
MOD=1_000_000_007
class Solution:
    def numberOfCombinations(self, num: str) -> int:
        if not num or num[0]=='0': return 0
        n=len(num)
        lcp=[array('H',[0])*(n+1) for _ in range(n+1)]
        for i in range(n-1,-1,-1):
            ri=lcp[i]; rin=lcp[i+1]; ci=num[i]
            for j in range(n-1,i,-1):
                if ci==num[j]: ri[j]=rin[j+1]+1
        ps=[array('I',[0])*n for _ in range(n+1)]
        for end in range(1,n+1):
            row=ps[end]; acc=0
            for start in range(end):
                ways=0
                if num[start]!='0':
                    if start==0:
                        ways=1
                    else:
                        length=end-start
                        prev=ps[start]
                        lower=max(0,start-length+1)
                        ways=(prev[start-1]-(prev[lower-1] if lower else 0))%MOD
                        eq=start-length
                        if eq>=0:
                            common=lcp[eq][start]
                            if common>=length or num[eq+common]<=num[start+common]:
                                exact=(prev[eq]-(prev[eq-1] if eq else 0))%MOD
                                ways=(ways+exact)%MOD
                acc=(acc+ways)%MOD; row[start]=acc
        return int(ps[n][n-1])
