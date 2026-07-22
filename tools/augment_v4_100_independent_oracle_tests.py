"""Append deterministic small-oracle regression tests found by the v4 audit.

This tool is intentionally fail-closed: every generated expectation is computed by
an algorithm structurally independent from the accepted solution, and the accepted
solution must agree before the trusted hidden-test file is changed.
"""
from __future__ import annotations

import importlib.util
import json
import random
from itertools import combinations
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parents[1]
SEED = 20260722


def _load_solution(problem: str):
    path = ROOT / "examples" / problem / "accepted.py"
    spec = importlib.util.spec_from_file_location(problem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.Solution()


def _expr_value(s: str) -> int:
    def atom(i: int):
        if s[i] in "01": return int(s[i]), i + 1
        value, i = expression(i + 1)
        assert s[i] == ")"
        return value, i + 1
    def expression(i: int):
        lhs, i = atom(i)
        while i < len(s) and s[i] in "&|":
            op = s[i]; rhs, i = atom(i + 1)
            lhs = (lhs & rhs) if op == "&" else (lhs | rhs)
        return lhs, i
    return expression(0)[0]


def _expr_flip_cost(s: str) -> int:
    positions = [i for i, c in enumerate(s) if c in "01&|"]
    want = 1 - _expr_value(s)
    for count in range(1, len(positions) + 1):
        for changed in combinations(positions, count):
            t = list(s)
            for pos in changed:
                t[pos] = {"0": "1", "1": "0", "&": "|", "|": "&"}[t[pos]]
            if _expr_value("".join(t)) == want:
                return count
    return 1


def _cases_1782(rng):
    out=[]
    for _ in range(80):
        n=rng.randint(2,7); edges=[[1,2]]
        for _ in range(rng.randint(0,15)):
            a,b=rng.sample(range(1,n+1),2); edges.append([a,b])
        q=[rng.randint(0,2*len(edges)) for _ in range(rng.randint(1,6))]
        deg=[0]*(n+1); multi={}
        for a,b in edges:
            deg[a]+=1; deg[b]+=1; k=tuple(sorted((a,b))); multi[k]=multi.get(k,0)+1
        ans=[sum(deg[a]+deg[b]-multi.get((a,b),0)>x for a in range(1,n+1) for b in range(a+1,n+1)) for x in q]
        out.append(([n,edges,q],ans))
    return out


def _rand_expr(rng, depth):
    if depth == 0 or rng.random() < .35: return rng.choice("01")
    return "("+_rand_expr(rng,depth-1)+rng.choice("&|")+_rand_expr(rng,depth-1)+")"


def _cases_1896(rng):
    return [([s],_expr_flip_cost(s)) for s in (_rand_expr(rng,rng.randint(1,3)) for _ in range(70))]


def _cases_2809(rng):
    import itertools
    out=[]
    for _ in range(55):
        n=rng.randint(1,7); a=[rng.randint(0,12) for _ in range(n)]; b=[rng.randint(0,8) for _ in range(n)]; x=rng.randint(0,100)
        ans=-1
        for t in range(n+1):
            best=0
            for p in itertools.permutations(range(n),t): best=max(best,sum(a[i]+(j+1)*b[i] for j,i in enumerate(p)))
            if sum(a)+t*sum(b)-best <= x: ans=t; break
        out.append(([a,b,x],ans))
    return out


def _cases_2940(rng):
    out=[]
    for _ in range(85):
        n=rng.randint(1,10); h=[rng.randint(1,20) for _ in range(n)]; qs=[[rng.randrange(n),rng.randrange(n)] for __ in range(rng.randint(1,12))]
        ans=[]
        for a,b in qs:
            if a==b: ans.append(a); continue
            a,b=sorted((a,b))
            if h[a]<h[b]: ans.append(b); continue
            ans.append(next((i for i in range(b+1,n) if h[i]>h[a]),-1))
        out.append(([h,qs],ans))
    return out


def _cases_2945(rng):
    out=[]
    for _ in range(75):
        a=[rng.randint(1,12) for __ in range(rng.randint(1,9))]; n=len(a); best=1
        for mask in range(1<<(n-1)):
            sums=[]; cur=a[0]
            for i in range(n-1):
                if mask>>i&1: sums.append(cur); cur=a[i+1]
                else: cur+=a[i+1]
            sums.append(cur)
            if all(sums[i]<=sums[i+1] for i in range(len(sums)-1)): best=max(best,len(sums))
        out.append(([a],best))
    return out


def _cases_3117(rng):
    out=[]
    for _ in range(85):
        a=[rng.randint(0,31) for __ in range(rng.randint(1,8))]; target=[rng.randint(0,31) for __ in range(rng.randint(1,len(a)))]
        @lru_cache(None)
        def dp(pos,g):
            if g==len(target): return 0 if pos==len(a) else 10**9
            value=(1<<30)-1; best=10**9
            for end in range(pos,len(a)):
                value &= a[end]
                if value==target[g]: best=min(best,a[end]+dp(end+1,g+1))
            return best
        v=dp(0,0); out.append(([a,target],-1 if v>=10**9 else v))
    return out


SPECS={
 "lc-1782-count-pairs-of-nodes": ("countPairs",_cases_1782),
 "lc-1896-minimum-cost-to-change-the-final-value-of-expression": ("minOperationsToFlip",_cases_1896),
 "lc-2809-minimum-time-to-make-array-sum-at-most-x": ("minimumTime",_cases_2809),
 "lc-2940-find-building-where-alice-and-bob-can-meet": ("leftmostBuildingQueries",_cases_2940),
 "lc-2945-find-maximum-non-decreasing-array-length": ("findMaximumLength",_cases_2945),
 "lc-3117-minimum-sum-of-values-by-dividing-array": ("minimumValueSum",_cases_3117),
}


def main():
    rng=random.Random(SEED); changes=[]
    for problem,(method,build) in SPECS.items():
        generated=build(rng); solution=_load_solution(problem); path=ROOT/"examples"/problem/"hidden_tests.json"; tests=json.loads(path.read_text(encoding="utf-8"))
        existing={json.dumps(x["args"],sort_keys=True,separators=(",",":")) for x in tests}; added=[]
        for args, expected in generated:
            actual=getattr(solution,method)(*args)
            if actual != expected: raise RuntimeError(f"accepted reference mismatch for {problem}")
            key=json.dumps(args,sort_keys=True,separators=(",",":"))
            if key not in existing:
                added.append({"args":args,"expected":expected}); existing.add(key)
        if added:
            tests.extend(added); path.write_text(json.dumps(tests,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
        changes.append((problem,len(added)))
    print("Independent-oracle tests appended:")
    for problem,count in changes: print(f"{problem}: {count}")

if __name__ == "__main__": main()
