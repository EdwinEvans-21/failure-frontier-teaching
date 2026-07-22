"""Read-only Docker recheck of Student AC code on fresh independent small oracles.

Only aggregate verdicts and artifact-relative paths are persisted; generated test
arguments and expected values stay temporary and are deleted after each judge call.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/"src"))
from ffjudge.runner import DockerJudge
sys.path.insert(0,str(ROOT/"tools"))
import augment_v4_100_independent_oracle_tests as oracle


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("run_dir",type=Path); parser.add_argument("--per-problem",type=int,default=25); parser.add_argument("--role",choices=("student","teacher"),default="student")
    args=parser.parse_args(); run=args.run_dir.resolve(); inventory=json.loads((run/"submission_algorithm_inventory.json").read_text(encoding="utf-8"))
    rng=random.Random(oracle.SEED+1); tests={}
    for problem,(_,build) in oracle.SPECS.items():
        generated=build(rng)[:args.per_problem]
        solution=oracle._load_solution(problem); method=oracle.SPECS[problem][0]
        for call,expected in generated:
            if getattr(solution,method)(*call)!=expected: raise RuntimeError(f"reference disagreement: {problem}")
        tests[problem]=[{"args":call,"expected":expected} for call,expected in generated]
    candidates=[row for row in inventory["rows"] if ((row["condition"]=="teacher") if args.role=="teacher" else (row["condition"]!="teacher")) and row["verdict"]=="AC" and row["problem_id"] in tests]
    judge=DockerJudge(); judge.build_image(ROOT); rows=[]
    for row in candidates:
        source=run/row["submission_path"]; submission=json.loads(source.read_text(encoding="utf-8")); code_path=Path(submission["result"]["artifact_paths"]["submission"])
        with tempfile.NamedTemporaryFile(mode="w",suffix=".json",delete=False,encoding="utf-8") as handle:
            json.dump(tests[row["problem_id"]],handle); temp=Path(handle.name)
        try:
            result=judge.judge(code_path,ROOT/"examples"/row["problem_id"]/"problem.json",temp,phase="hidden")
            verdict=result.verdict.name
        finally:
            temp.unlink(missing_ok=True)
        rows.append({key:row[key] for key in ("problem_id","condition","generation","code_sha256","submission_path")}|{"fresh_small_oracle_verdict":verdict})
        print(f"{row['problem_id']} {row['condition']} {row['code_sha256'][:12]} {verdict}",flush=True)
    report={"schema_version":"1.0","scope":f"{args.role} AC only; fresh independent small-oracle Docker replay","generated_case_count_per_problem":args.per_problem,"candidate_count":len(rows),"all_passed":all(row["fresh_small_oracle_verdict"]=="ACCEPTED" for row in rows),"rows":rows}
    (run/f"{args.role}_ac_small_oracle_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"candidate_count":len(rows),"all_passed":report["all_passed"]}))

if __name__=="__main__": main()
