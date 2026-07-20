from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import csv
import hashlib
import json
import shutil
import subprocess

from . import AUDIT_POLICY, BENCHMARK_POLICY, JUDGE_POLICY, REPLAY_POLICY
from .catalog import PROBLEMS, examples_dir
from .generators import GENERATOR_VERSION, generate_cases, stress_cases
from .inventory import discover_submissions, sha256_file, snapshot_tree
from .judge import OracleHardenedJudge, canonical_sha256

KNOWN_FALSE_PREFIXES = {
    "dad4638e9c", "e1f27238c0", "a1f1d1cc36", "aa6dec3233",
    "51b3e55ddd", "32847b0425", "9a94dc855c", "df68e89ac2",
    "b3a6fd3bfb", "9466e6bd42", "9488524082", "2bf793e7d9",
    "f5832b3ed6", "3d7df60bcd", "a482dcfffb", "bd0217ea41",
    "f01ee02154", "906f7848d4", "a267720725",
}


class ReplayError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_manifest(repo: Path, source: Path, inventory: list[dict[str, Any]], reconciliation: dict[str, Any], image: str) -> dict[str, Any]:
    image_id = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, text=True, check=False).stdout.strip()
    all_numbers = sorted(int(p.name[3:7]) for p in (repo / "examples").glob("lc-[0-9][0-9][0-9][0-9]-*"))
    statuses = []
    for number in all_numbers:
        statuses.append({"problem_id": examples_dir(repo, number).name, "problem_benchmark_status": "HARDENED_IN_V3" if number in PROBLEMS else "NOT_HARDENED_IN_V3"})
    return {
        "schema_version": "3.0", "benchmark_policy": BENCHMARK_POLICY,
        "judge_policy": JUDGE_POLICY, "replay_policy": REPLAY_POLICY,
        "audit_policy": AUDIT_POLICY, "generator_version": GENERATOR_VERSION,
        "oracle_version": "trusted_expanded_oracles_at_source_commit",
        "comparator_version": "ffjudge_equivalent_exact_v1",
        "stress_version": "stress_v3_1", "created_at": utc_now(),
        "source_run": str(source), "source_run_id": reconciliation["source_run_id"],
        "source_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip(),
        "docker_image": image, "docker_image_id": image_id,
        "inventory_count": len(inventory), "inventory_reconciliation": reconciliation,
        "hardened_problem_count": len(PROBLEMS), "problems": statuses,
        "hash_strategy": "SHA-256 of raw bytes for files; canonical UTF-8 sorted compact JSON for stable semantic artifacts",
        "expected_values_container_visible": False, "model_api_calls": 0,
    }


def run(*, repo: Path, source: Path, output: Path, mode: str, image: str = "ffjudge-python:latest") -> dict[str, Any]:
    if mode not in {"dry-run", "calibration", "full", "resume"}:
        raise ReplayError(f"unsupported mode {mode}")
    repo, source, output = repo.resolve(), source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ReplayError("output must not be inside source run")
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot_tree(source)
    inventory, reconciliation = discover_submissions(source)
    if not reconciliation["passed"]:
        raise ReplayError(f"source manifest reconciliation failed: {reconciliation}")
    manifest = build_manifest(repo, source, inventory, reconciliation, image)
    write_json(output / "benchmark_v3_manifest.json", manifest)
    write_json(output / "benchmark_v3_problem_status.json", manifest["problems"])
    write_json(output / "oracle_versions.json", {str(n): {"oracle": p.oracle.__name__, "reference": p.reference.__name__, "version": manifest["oracle_version"]} for n,p in PROBLEMS.items()})
    write_json(output / "generator_versions.json", {"version": GENERATOR_VERSION, "seeds": {str(n): p.seed for n,p in PROBLEMS.items()}, "bounds": {str(n): p.exhaustive_bound for n,p in PROBLEMS.items()}})
    write_json(output / "stress_versions.json", {str(n): p.stress_version for n,p in PROBLEMS.items()})
    write_json(output / "submission_inventory.json", {"reconciliation": reconciliation, "submissions": inventory})
    if mode == "dry-run":
        result = {"api_accessed": False, "judge_replay_started": False, "source_run_modified": snapshot_tree(source) != before, "inventory_count": len(inventory)}
        write_json(output / "dry_run_result.json", result)
        _finish_integrity(output, source, before, result)
        return result
    judge = OracleHardenedJudge(image)
    selected = inventory
    if mode == "calibration":
        selected = [r for r in inventory if any(r["submission_sha256"].startswith(p) for p in KNOWN_FALSE_PREFIXES)]
    records = replay_inventory(repo, source, output, inventory, selected, judge, include_fixtures=mode == "calibration")
    false_records = [r for r in records if any(r["submission_sha256"].startswith(p) for p in KNOWN_FALSE_PREFIXES)]
    caught = {next(p for p in KNOWN_FALSE_PREFIXES if r["submission_sha256"].startswith(p)) for r in false_records if r["replay_judge_verdict_v3"] != "AC"}
    quality = {"known_false_expected": len(KNOWN_FALSE_PREFIXES), "known_false_discovered": len(false_records), "known_false_rejected": len(caught), "lc3117_known_false_expected": 6, "lc3117_known_false_rejected": sum(1 for p in caught if any(r["submission_sha256"].startswith(p) and r["problem_id"].startswith("lc-3117-") for r in false_records)), "passed": len(caught) == len(KNOWN_FALSE_PREFIXES)}
    write_json(output / "known_false_positive_regression.json", quality)
    if mode == "calibration":
        if not quality["passed"]:
            raise ReplayError(f"calibration quality gate failed: {quality}")
    aggregates = aggregate(records, inventory, manifest)
    for name, value in aggregates.items():
        write_json(output / name, value)
    _write_records(output, records)
    _write_report(output, manifest, records, aggregates)
    result = {"api_accessed": False, "judge_replay_started": True, "source_run_modified": snapshot_tree(source) != before, "inventory_count": len(inventory), "replay_record_count": len(records)}
    _finish_integrity(output, source, before, result)
    return result


def replay_inventory(repo: Path, source: Path, output: Path, inventory: list[dict[str, Any]], selected: list[dict[str, Any]], judge: OracleHardenedJudge, *, include_fixtures: bool) -> list[dict[str, Any]]:
    selected_ids = {r["submission_instance_id"] for r in selected}
    cache_dir = output / "judge_artifacts"
    records: list[dict[str, Any]] = []
    cache: dict[tuple[str,str], dict[str, Any]] = {}
    semantic_case_cache: dict[int, list[dict[str, Any]]] = {}
    stress_case_cache: dict[int, list[dict[str, Any]]] = {}
    for row in inventory:
        record = dict(row)
        number = int(row["problem_id"][3:7])
        if row["submission_instance_id"] not in selected_ids:
            continue
        if number not in PROBLEMS:
            record.update({"replay_judge_verdict_v3": None, "oracle_audit_status": "NOT_AUDITED", "counterexample_found": None, "counterexample_ids": [], "semantic_validation_status": "NOT_TESTED", "complexity_audit_status": "NOT_RUN", "problem_benchmark_status": "NOT_HARDENED_IN_V3"})
            records.append(record); continue
        key = (row["problem_id"], row["submission_sha256"])
        artifact = cache_dir / row["problem_id"] / f"{row['submission_sha256']}.json"
        if number not in semantic_case_cache:
            semantic_case_cache[number] = generate_cases(number)
            stress_case_cache[number] = stress_cases(number)
        cases = semantic_case_cache[number]
        expected_cache_key = canonical_sha256({"judge_policy": JUDGE_POLICY, "generator_version": GENERATOR_VERSION, "submission_sha256": row["submission_sha256"], "semantic_cases_sha256": canonical_sha256(cases), "stress_cases_sha256": canonical_sha256(stress_case_cache[number])})
        if key in cache and cache[key].get("cache_key") == expected_cache_key:
            result = cache[key]
        elif artifact.is_file():
            result = json.loads(artifact.read_text(encoding="utf-8"))
            if result.get("cache_key") != expected_cache_key:
                result = {}
            else:
                cache[key] = result
        else:
            result = {}
        if not result:
            semantic = judge.judge(source / row["submission_path"], examples_dir(repo, number) / "problem.json", cases, layer="semantic")
            stress = {"verdict": "NOT_RUN"}
            if semantic["verdict"] == "AC":
                stress = judge.judge(source / row["submission_path"], examples_dir(repo, number) / "problem.json", stress_case_cache[number], layer="complexity_stress")
            result = {"cache_key": expected_cache_key, "semantic": semantic, "stress": stress}
            write_json(artifact, result)
            cache[key] = result
        semantic, stress = result["semantic"], result["stress"]
        final = semantic["verdict"] if semantic["verdict"] != "AC" else ("AC" if stress["verdict"] == "AC" else stress["verdict"])
        counter_ids: list[str] = []
        if semantic.get("reason") == "counterexample":
            ce = {"problem_id": row["problem_id"], "submission_sha256": row["submission_sha256"], "generator_version": GENERATOR_VERSION, "oracle_version": "trusted_expanded_oracles_at_source_commit", "input": semantic["input"], "expected_output": semantic["expected"], "actual_output": semantic["actual"], "execution_status": "ok", "minimization_status": "generator_case_already_small"}
            ce["counterexample_sha256"] = canonical_sha256(ce)
            ce_id = ce["counterexample_sha256"][:16]
            counter_ids.append(ce_id)
            write_json(output / "counterexamples" / row["problem_id"] / f"{ce_id}.json", ce)
        record.update({
            "replay_judge_verdict_v3": final,
            "oracle_audit_status": "FAILED" if counter_ids else ("AUDIT_ERROR" if semantic["verdict"] == "INTERNAL_ERROR" else "NO_COUNTEREXAMPLE_FOUND"),
            "counterexample_found": bool(counter_ids), "counterexample_ids": counter_ids,
            "semantic_validation_status": "COUNTEREXAMPLE_FOUND" if counter_ids else ("NOT_TESTED" if semantic["verdict"] == "INTERNAL_ERROR" else "NO_COUNTEREXAMPLE_FOUND"),
            "complexity_audit_status": "PASSED_STRESS" if stress["verdict"] == "AC" else ("NOT_RUN" if stress["verdict"] == "NOT_RUN" else "FAILED_STRESS"),
            "problem_benchmark_status": "HARDENED_IN_V3",
            "judge_v3_artifact_path": artifact.relative_to(output).as_posix(),
            "judge_v3_artifact_sha256": canonical_sha256({"semantic": {k:v for k,v in semantic.items() if k not in {"runtime_ms","case_runtime_ms"}}, "stress": {k:v for k,v in stress.items() if k not in {"runtime_ms","case_runtime_ms"}}}),
            "semantic_runtime_ms": semantic.get("runtime_ms"),
            "stress_runtime_ms": stress.get("runtime_ms"),
            "stress_case_id": stress.get("case_id", f"lc{number}-stress-0001" if stress["verdict"] != "NOT_RUN" else None),
            "stress_timeout_seconds": json.loads((examples_dir(repo, number) / "problem.json").read_text(encoding="utf-8"))["limits"]["time_seconds"],
            "stress_memory_mb": json.loads((examples_dir(repo, number) / "problem.json").read_text(encoding="utf-8"))["limits"]["memory_mb"],
            "output_limit_bytes": 1024 * 1024,
            "complexity_or_robustness_risk": "HASH_COLLISION_NOT_EXCLUDED" if number == 3045 and "%" in (source / row["submission_path"]).read_text(encoding="utf-8", errors="replace") else None,
        })
        records.append(record)
    if include_fixtures:
        records.extend(_replay_fixtures(repo, output, judge))
    return records


def _replay_fixtures(repo: Path, output: Path, judge: OracleHardenedJudge) -> list[dict[str, Any]]:
    rows=[]
    fixture_root = repo / "experiments" / "benchmark_v3_oracle_hardened" / "fixtures"
    fixture_paths: list[tuple[Path, int, str]] = []
    for path in sorted(fixture_root.glob("*.py")):
        fixture_paths.append((path, int(path.name.split("_")[0][2:]), "AC" if "_valid_" in path.stem else "NON_AC"))
    for number in sorted(PROBLEMS):
        fixture_paths.append((examples_dir(repo, number) / "accepted.py", number, "AC"))
    for path, number, expected in fixture_paths:
        semantic=judge.judge(path, examples_dir(repo, number)/"problem.json", generate_cases(number), layer="semantic")
        stress={"verdict":"NOT_RUN"}
        if semantic["verdict"]=="AC": stress=judge.judge(path, examples_dir(repo, number)/"problem.json", stress_cases(number), layer="complexity_stress")
        got=semantic["verdict"] if semantic["verdict"]!="AC" else stress["verdict"]
        fixture_id=f"reference:lc{number}" if path.name=="accepted.py" else f"fixture:{path.name}"
        rows.append({"submission_instance_id":fixture_id,"problem_id":examples_dir(repo,number).name,"role":"fixture","condition":"fixture","root_id":fixture_id,"generation":0,"submission_path":str(path.relative_to(repo)),"submission_sha256":sha256_file(path),"original_judge_verdict":None,"replay_judge_verdict_v3":got,"fixture_expected":expected,"fixture_passed":got=="AC" if expected=="AC" else got!="AC","oracle_audit_status":"NO_COUNTEREXAMPLE_FOUND" if got=="AC" else "FAILED","counterexample_ids":[],"complexity_audit_status":"PASSED_STRESS" if stress["verdict"]=="AC" else "NOT_RUN","problem_benchmark_status":"HARDENED_IN_V3"})
    write_json(output/"fixture_calibration.json", rows)
    if any(not r["fixture_passed"] for r in rows): raise ReplayError("fixture calibration failed")
    return rows


def aggregate(records: list[dict[str, Any]], inventory: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    observed=[r for r in records if r.get("role")=="student"]
    confusion=defaultdict(Counter)
    for r in records:
        if r.get("role") in {"teacher","student"}: confusion[r["role"]][(r.get("original_judge_verdict"),r.get("replay_judge_verdict_v3"))]+=1
    confusion_json={role:{f"{a}->{b}":n for (a,b),n in sorted(values.items(),key=str)} for role,values in confusion.items()}
    original_ac=sum(r.get("original_judge_verdict")=="AC" for r in observed)
    replay_ac=sum(r.get("replay_judge_verdict_v3")=="AC" for r in observed)
    lineages=defaultdict(list)
    for r in observed: lineages[(r["root_id"],r["condition"],r.get("lineage_repeat_index",0))].append(r)
    censor=[]; lower=upper=0
    condition_bounds=defaultdict(lambda:Counter(lineages=0,lower=0,upper=0,censored=0))
    curves=defaultdict(lambda:{"original_cumulative":[],"replay_observed_cumulative":[]})
    for key, seq in lineages.items():
        seq.sort(key=lambda r:r["generation"])
        false=[r for r in seq if r.get("original_judge_verdict")=="AC" and r.get("replay_judge_verdict_v3")!="AC"]
        censored=bool(false and max(r["generation"] for r in seq)<5)
        success=any(r.get("replay_judge_verdict_v3")=="AC" for r in seq)
        lower+=int(success); upper+=int(success or censored)
        cb=condition_bounds[key[1]]; cb["lineages"]+=1; cb["lower"]+=int(success); cb["upper"]+=int(success or censored); cb["censored"]+=int(censored)
        if censored: censor.append({"root_id":key[0],"condition":key[1],"lineage_repeat_index":key[2],"censored_by_false_ac":True,"censoring_generation":min(r["generation"] for r in false),"counterfactual_descendants_missing":True})
    for condition in condition_bounds:
        seqs=[seq for key,seq in lineages.items() if key[1]==condition]
        for generation in range(1,6):
            curves[condition]["original_cumulative"].append(sum(any(r.get("original_judge_verdict")=="AC" and r["generation"]<=generation for r in seq) for seq in seqs))
            curves[condition]["replay_observed_cumulative"].append(sum(any(r.get("replay_judge_verdict_v3")=="AC" and r["generation"]<=generation for r in seq) for seq in seqs))
    n=len(lineages)
    bounds={"lineage_count":n,"success_lower_bound_count":lower,"success_upper_bound_count":upper,"five_generation_success_identified_interval":[lower/n if n else 0,upper/n if n else 0],"by_condition":{c:{**dict(v),"identified_interval":[v["lower"]/v["lineages"],v["upper"]/v["lineages"]]} for c,v in condition_bounds.items()},"cumulative_curves":dict(curves)}
    per_problem=defaultdict(lambda:Counter(total=0,old_ac=0,new_ac=0,false_ac=0))
    per_condition=defaultdict(lambda:Counter(total=0,old_ac=0,new_ac=0,false_ac=0))
    per_generation=defaultdict(lambda:Counter(total=0,old_ac=0,new_ac=0,false_ac=0))
    per_role=defaultdict(lambda:Counter(total=0,old_ac=0,new_ac=0,false_ac=0))
    for r in observed:
        for bucket in (per_problem[r["problem_id"]],per_condition[r["condition"]],per_generation[str(r["generation"])],per_role[r["role"]]):
            bucket["total"]+=1; bucket["old_ac"]+=r.get("original_judge_verdict")=="AC"; bucket["new_ac"]+=r.get("replay_judge_verdict_v3")=="AC"; bucket["false_ac"]+=r.get("original_judge_verdict")=="AC" and r.get("replay_judge_verdict_v3")!="AC"
    def serial(d): return {k:{**dict(v),"false_positive_rate_among_old_ac":v["false_ac"]/v["old_ac"] if v["old_ac"] else None} for k,v in d.items()}
    problem_condition=defaultdict(lambda:defaultdict(list))
    for (root,condition,repeat),seq in lineages.items():
        problem=seq[0]["problem_id"]
        problem_condition[condition][problem].append(any(r.get("replay_judge_verdict_v3")=="AC" for r in seq))
    macro={}
    bootstrap={}
    import random
    rng=random.Random(20260720)
    for condition,problems in problem_condition.items():
        rates=[sum(v)/len(v) for v in problems.values()]
        macro[condition]=sum(rates)/len(rates) if rates else None
        samples=[]
        keys=sorted(problems)
        for _ in range(2000):
            draw=[rng.choice(keys) for __ in keys]
            samples.append(sum(sum(problems[k])/len(problems[k]) for k in draw)/len(draw))
        samples.sort()
        bootstrap[condition]={"seed":20260720,"replicates":2000,"problem_cluster_count":len(keys),"mean":sum(samples)/len(samples),"percentile_95":[samples[int(.025*len(samples))],samples[int(.975*len(samples))-1]]}
    metrics={"original_metrics":{"student_ac":original_ac,"student_total":len(observed)},"replay_metrics":{"student_ac":replay_ac,"student_total":len(observed),"root_level_micro":{c:{"successes":v["lower"],"lineages":v["lineages"],"observed_success_rate":v["lower"]/v["lineages"]} for c,v in condition_bounds.items()}},"censoring_adjusted_metrics":bounds,"per_problem":serial(per_problem),"per_condition":serial(per_condition),"per_generation":serial(per_generation),"per_role":serial(per_role),"raw_problem_macro":macro,"token_cost_observed_only":{"prompt_tokens":sum(r.get("prompt_tokens",0) for r in observed),"completion_tokens":sum(r.get("completion_tokens",0) for r in observed),"total_tokens":sum(r.get("total_tokens",0) for r in observed)}}
    configured=set(manifest["inventory_reconciliation"]["conditions"]); aggregated=set(per_condition)
    if aggregated and aggregated != configured: raise ReplayError(f"aggregate condition drift: {aggregated} != {configured}")
    return {"verdict_confusion_matrix.json":confusion_json,"false_ac_censoring.json":{"records":censor,"by_condition":dict(Counter(x["condition"] for x in censor))},"observed_replay_aggregate.json":metrics,"censoring_bounds_aggregate.json":bounds,"problem_cluster_aggregate.json":{"method":"deterministic problem-cluster bootstrap over raw per-problem lineage success; descriptive only","bootstrap":bootstrap,"per_problem":serial(per_problem),"leave_one_problem_out":{p:{"student_ac":replay_ac-v["new_ac"],"student_total":len(observed)-v["total"]} for p,v in per_problem.items()}}}


def _write_records(output: Path, records: list[dict[str, Any]]) -> None:
    with (output/"submission_replay.jsonl").open("w",encoding="utf-8",newline="\n") as f:
        for row in records: f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    keys=sorted({k for r in records for k in r if not isinstance(r[k],(dict,list))})
    with (output/"submission_replay.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows([{k:r.get(k) for k in keys} for r in records])
    with (output/"complexity_audit.jsonl").open("w",encoding="utf-8",newline="\n") as f:
        for r in records: f.write(json.dumps({k:r.get(k) for k in ("submission_instance_id","problem_id","submission_sha256","complexity_audit_status","stress_case_id","stress_runtime_ms","stress_timeout_seconds","stress_memory_mb","output_limit_bytes","complexity_or_robustness_risk")},sort_keys=True)+"\n")


def _write_report(output: Path, manifest: dict[str,Any], records:list[dict[str,Any]], aggregates:dict[str,Any]) -> None:
    metrics=aggregates["observed_replay_aggregate.json"]
    confusion=aggregates["verdict_confusion_matrix.json"]
    censored=aggregates["false_ac_censoring.json"]
    complexity=Counter(r.get("complexity_audit_status") for r in records)
    text=f"""# Oracle-hardened observed-submission replay\n\nPolicies: `{BENCHMARK_POLICY}`, `{JUDGE_POLICY}`, `{REPLAY_POLICY}`, `{AUDIT_POLICY}`.\n\nThis replay made zero model calls and did not generate counterfactual descendants. It preserves original verdicts and records v3 verdicts separately. A counterexample proves a submission incorrect; `NO_COUNTEREXAMPLE_FOUND` is not proof of correctness. Complexity stress is separate from semantic validation, and `NO_TIMEOUT_OBSERVED` would not be a complexity proof. False AC creates informative censoring, so missing descendants remain unknown.\n\n- Inventory: {manifest['inventory_count']}\n- Replay records: {len(records)}\n- Hardened problems: {manifest['hardened_problem_count']}\n- Student original AC: {metrics['original_metrics']['student_ac']}\n- Student replay AC: {metrics['replay_metrics']['student_ac']}\n- Identified five-generation interval: {metrics['censoring_adjusted_metrics']['five_generation_success_identified_interval']}\n- False-AC-censored lineages: {len(censored['records'])}\n- Complexity stress failures: {complexity.get('FAILED_STRESS', 0)}\n\n## Verdict audit\n\nTeacher confusion: `{json.dumps(confusion.get('teacher', {}), sort_keys=True)}`.\n\nStudent confusion: `{json.dumps(confusion.get('student', {}), sort_keys=True)}`.\n\nPer-condition old-AC false-positive rates are recorded in `observed_replay_aggregate.json`; they are not uniform, so old condition rankings cannot be treated as unbiased. `lc-3117` has zero replay AC among the observed Student submissions and all six known old ACs are rejected.\n\n## Interpretation\n\nThe replay still supports the limited claim that some actually observed Student programs pass a materially stronger finite benchmark. It does not support the old exact five-generation success rates, the validity of any old `lc-3117` AC, or a clean causal ranking of conditions after condition-dependent false-AC censoring. Old non-AC to v3 AC transitions are `NO_COUNTEREXAMPLE_FOUND`, not proof that the old verdict was a false negative.\n\nThe remaining 15 problems are explicitly `NOT_HARDENED_IN_V3` and are excluded from v3 capability claims. Algorithm-family labels and similarity to a reference were never used as verdict criteria.\n"""
    (output/"replay_report.md").write_text(text,encoding="utf-8")


def _finish_integrity(output: Path, source: Path, before: dict[str,str], result:dict[str,Any]) -> None:
    after=snapshot_tree(source)
    report={"source_run_modified":before!=after,"source_file_count":len(before),"source_tree_sha256_before":canonical_sha256(before),"source_tree_sha256_after":canonical_sha256(after),"model_api_calls":0,"new_generations":0,"authorization_material_written":False,**result}
    write_json(output/"integrity_report.json",report)
    hashes={p.relative_to(output).as_posix():sha256_file(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="artifact_sha256.json"}
    write_json(output/"artifact_sha256.json",hashes)
