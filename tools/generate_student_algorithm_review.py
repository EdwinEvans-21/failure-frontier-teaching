"""Produce the reviewed Student-AC disposition ledger from static and oracle audits."""
from __future__ import annotations

import argparse, json
from collections import Counter
from pathlib import Path

EQUIVALENT = {
 "lc-1187-make-array-strictly-increasing":"value-map DP is equivalent to the standard frontier DP",
 "lc-1240-tiling-a-rectangle-with-the-fewest-squares":"height-profile and bitmask searches enumerate the same canonical tilings",
 "lc-1312-minimum-insertion-steps-to-make-a-string-palindrome":"interval insertion DP and n minus LPS are equivalent formulations",
 "lc-1388-pizza-with-3n-slices":"two linear non-adjacent-selection cases are the standard circle reduction",
 "lc-1416-restore-the-array":"top-down and suffix bottom-up partition DP are equivalent",
 "lc-1575-count-all-possible-routes":"top-down and bottom-up fuel DP are equivalent",
 "lc-1632-rank-transform-of-a-matrix":"per-value DSU grouping is an equivalent standard rank propagation formulation",
 "lc-1851-minimum-interval-to-include-each-query":"coordinate/segment assignment and left-sweep min-heap answer the same interval minimum query",
 "lc-1872-stone-game-viii":"prefix and suffix backward recurrences are algebraic rearrangements",
 "lc-1889-minimum-space-wasted-from-packaging":"two-pointer and binary-search supplier packing are equivalent sorted-prefix accounting",
 "lc-2045-second-minimum-time-to-reach-destination":"two-arrival BFS and heap Dijkstra are equivalent under uniform edge traversal time",
 "lc-2092-find-all-people-with-secret":"same-time component BFS and temporary DSU realize the same simultaneous propagation rule",
 "lc-2106-maximum-fruits-harvested-after-at-most-k-steps":"prefix enumeration and sliding window use the same interval travel-cost constraint",
 "lc-2163-minimum-difference-in-sums-after-removal-of-elements":"heap prefix/suffix formulations are equivalent boundary minimization",
 "lc-3045-count-prefix-and-suffix-pairs-ii":"KMP border enumeration and trie accounting are equivalent prefix/suffix counting strategies",
}

ORACLE = {
 "lc-1547-minimum-cost-to-cut-a-stick", "lc-1771-maximize-palindrome-length-from-subsequences",
 "lc-1782-count-pairs-of-nodes", "lc-1896-minimum-cost-to-change-the-final-value-of-expression",
 "lc-2809-minimum-time-to-make-array-sum-at-most-x", "lc-2940-find-building-where-alice-and-bob-can-meet",
 "lc-2945-find-maximum-non-decreasing-array-length", "lc-3117-minimum-sum-of-values-by-dividing-array",
}

def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('run_dir',type=Path);args=parser.parse_args();run=args.run_dir.resolve()
    inventory=json.loads((run/'submission_algorithm_inventory.json').read_text(encoding='utf-8'))
    oracle_rows=[]
    for name in ('student_ac_small_oracle_audit.json','student_nonobvious_algorithm_oracle_audit.json'):
        data=json.loads((run/name).read_text(encoding='utf-8'))
        key='fresh_small_oracle_verdict' if name.startswith('student_ac_small') else 'independent_oracle_verdict'
        oracle_rows.extend((row['code_sha256'],row[key]) for row in data['rows'])
    oracle_verdict=dict(oracle_rows)
    rows=[]
    for row in inventory['rows']:
        if row['condition']=='teacher' or row['verdict']!='AC': continue
        problem=row['problem_id']; code=row['code_sha256']
        if problem in ORACLE:
            verdict=oracle_verdict.get(code)
            if verdict!='ACCEPTED': raise RuntimeError(f'missing or failed oracle result: {problem} {code}')
            disposition='independently_oracle_validated'; rationale='fresh small independent oracle replay accepted'
        elif problem in EQUIVALENT:
            disposition='obvious_equivalent_family'; rationale=EQUIVALENT[problem]
        else:
            disposition='obvious_standard_family'; rationale='algorithm structure and selected formulation match the problem canonical family'
        rows.append({'problem_id':problem,'condition':row['condition'],'generation':row['generation'],'code_sha256':code,'submission_path':row['submission_path'],'selected_algorithm':row['selected_algorithm'],'disposition':disposition,'rationale':rationale})
    counts=Counter(row['disposition'] for row in rows)
    report={'schema_version':'1.0','scope':'all Student AC submissions from the completed audit-v2 run','policy':'obvious standard families are not re-executed; obvious equivalent formulations receive an equivalence rationale; remaining families require fresh independent oracle replay','submission_count':len(rows),'disposition_counts':dict(sorted(counts.items())),'rows':rows}
    (run/'student_algorithm_review_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    lines=['# Student Algorithm Review Result','',f'- reviewed Student AC submissions: {len(rows)}']+[f'- {key}: {value}' for key,value in sorted(counts.items())]+['','No hidden inputs, expected values, or private judge diagnostics are included.']
    (run/'student_algorithm_review_result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'reviewed':len(rows),'disposition_counts':dict(counts)}))

if __name__=='__main__':main()
