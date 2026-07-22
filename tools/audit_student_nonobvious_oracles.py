"""Independent-oracle replay for Student AC algorithms needing semantic review."""
from __future__ import annotations

import argparse, json, random, sys, tempfile
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/"src"))
from ffjudge.runner import DockerJudge


def cut_oracle(n: int, cuts: list[int]) -> int:
    points=(0,*sorted(cuts),n)
    @lru_cache(None)
    def solve(left: int, right: int) -> int:
        return min((points[right]-points[left]+solve(left,k)+solve(k,right) for k in range(left+1,right)),default=0)
    return solve(0,len(points)-1)


def palindrome_oracle(a: str, b: str) -> int:
    s=a+b; split=len(a); best=0
    for mask in range(1,1<<len(s)):
        if not (mask & ((1<<split)-1)) or not (mask >> split): continue
        t=''.join(s[i] for i in range(len(s)) if mask>>i&1)
        if len(t)>best and t==t[::-1]: best=len(t)
    return best


def cases() -> dict[str,list[dict]]:
    rng=random.Random(20260724); out={"lc-1547-minimum-cost-to-cut-a-stick":[],"lc-1771-maximize-palindrome-length-from-subsequences":[]}
    for _ in range(45):
        n=rng.randint(2,18); cuts=sorted(rng.sample(range(1,n),rng.randint(0,min(n-1,7))))
        out["lc-1547-minimum-cost-to-cut-a-stick"].append({"args":[n,cuts],"expected":cut_oracle(n,cuts)})
    for _ in range(45):
        a=''.join(rng.choice('abc') for _ in range(rng.randint(1,6))); b=''.join(rng.choice('abc') for _ in range(rng.randint(1,6)))
        out["lc-1771-maximize-palindrome-length-from-subsequences"].append({"args":[a,b],"expected":palindrome_oracle(a,b)})
    return out


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('run_dir',type=Path);args=parser.parse_args();run=args.run_dir.resolve(); inventory=json.loads((run/'submission_algorithm_inventory.json').read_text(encoding='utf-8'))
    test_cases=cases(); candidates=[r for r in inventory['rows'] if r['condition']!='teacher' and r['verdict']=='AC' and r['problem_id'] in test_cases]
    judge=DockerJudge();judge.build_image(ROOT); rows=[]
    for row in candidates:
        submission=json.loads((run/row['submission_path']).read_text(encoding='utf-8')); source=Path(submission['result']['artifact_paths']['submission'])
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json',delete=False,encoding='utf-8') as h:json.dump(test_cases[row['problem_id']],h); temp=Path(h.name)
        try: verdict=judge.judge(source,ROOT/'examples'/row['problem_id']/'problem.json',temp,phase='hidden').verdict.name
        finally: temp.unlink(missing_ok=True)
        rows.append({key:row[key] for key in ('problem_id','condition','generation','code_sha256','submission_path')}|{'independent_oracle_verdict':verdict})
    report={'schema_version':'1.0','scope':'Student AC for non-obvious but plausible alternative families','cases_per_problem':45,'candidate_count':len(rows),'all_passed':all(x['independent_oracle_verdict']=='ACCEPTED' for x in rows),'rows':rows}
    (run/'student_nonobvious_algorithm_oracle_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'candidate_count':len(rows),'all_passed':report['all_passed']}))

if __name__=='__main__':main()
