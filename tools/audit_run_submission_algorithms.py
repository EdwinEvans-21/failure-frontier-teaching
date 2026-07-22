"""Read-only, reproducible algorithm inventory for an external experiment run.

The report deliberately contains no test inputs, expected values, or judge-private
diagnostics.  It indexes every judged submission with AST-level evidence so later
semantic review can distinguish code families without relying on filename or prompt
claims alone.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


SIGNALS = {
    "dynamic_programming": ("dp", "memo", "cache", "lru_cache"),
    "heap": ("heapq", "heappush", "heappop"),
    "deque": ("deque",),
    "binary_search": ("bisect", "bisect_left", "bisect_right"),
    "sorting": ("sort", "sorted"),
    "union_find": ("union", "find", "parent", "rank"),
    "bit_operations": ("bit_count", "<<", ">>", "&", "|", "^"),
    "recursion": ("recursion",),
}


def normalize(tree: ast.AST) -> str:
    class Names(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name):
            return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)
        def visit_arg(self, node: ast.arg):
            return ast.copy_location(ast.arg(arg="_", annotation=None), node)
    return ast.dump(Names().visit(tree), annotate_fields=False, include_attributes=False)


def features(code: str | None) -> dict:
    if not code:
        return {"parse_status": "missing", "normalized_ast_sha256": None, "node_counts": {}, "signals": [], "calls": [], "functions": []}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parse_status": "syntax_error", "normalized_ast_sha256": None, "node_counts": {}, "signals": [], "calls": [], "functions": []}
    nodes = Counter(type(x).__name__ for x in ast.walk(tree))
    calls = sorted({
        x.func.id if isinstance(x.func, ast.Name) else x.func.attr if isinstance(x.func, ast.Attribute) else "<dynamic>"
        for x in ast.walk(tree) if isinstance(x, ast.Call)
    })
    names = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name)} | set(calls)
    text = code.lower()
    signals = []
    for name, tokens in SIGNALS.items():
        if name == "recursion":
            funcs = {x.name for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if any(call in funcs for call in calls): signals.append(name)
        elif any(token in names or token in text for token in tokens): signals.append(name)
    return {
        "parse_status": "ok",
        "normalized_ast_sha256": hashlib.sha256(normalize(tree).encode()).hexdigest(),
        "node_counts": {key: nodes[key] for key in ("For", "While", "If", "FunctionDef", "ListComp", "DictComp", "Call", "Subscript") if nodes[key]},
        "signals": signals,
        "calls": calls,
        "functions": sorted(x.name for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)),
    }


def selected_algorithm(text: str | None) -> str | None:
    if not text: return None
    match = re.search(r"(?:##\s*Selected Algorithm|\*\*Selected Algorithm:?\*\*)(.*?)(?=\n##\s|\Z)", text, re.S | re.I)
    if not match: return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return value[:800] or None


def context(path: Path) -> dict:
    parts = path.parts
    condition = "teacher"
    generation = None
    if "lineages" in parts:
        i = parts.index("lineages"); lineage = parts[i + 1]
        condition = lineage.rsplit("__", 1)[-1]
        found = next((part for part in parts if part.startswith("generation_")), None)
        generation = int(found.rsplit("_", 1)[-1]) if found and found != "generation_000_root" else 0
    problem = next((part for part in parts if part.startswith("lc-")), None)
    if problem is None:
        lineage = next((part for part in parts if "__r" in part and "-t" in part), "")
        match = re.search(r"-t\d+-(lc-.+?)__r\d+__", lineage)
        problem = match.group(1) if match else None
    return {"condition": condition, "generation": generation, "problem_id": problem}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("run_dir", type=Path); parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(); run = args.run_dir.resolve(); output = args.output or run / "submission_algorithm_inventory.json"
    repo = Path(__file__).parents[1]
    references = {}
    for spec_path in (repo / "examples").glob("lc-*/problem.json"):
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
        references[spec["problem_id"]] = features((spec_path.parent / "accepted.py").read_text(encoding="utf-8-sig"))
    rows=[]
    for judge_path in sorted(run.rglob("judge.internal.json")):
        submission_path = judge_path.parent / "submission.json"
        if not submission_path.exists(): continue
        submission=json.loads(submission_path.read_text(encoding="utf-8")); result=submission.get("result", {})
        code=result.get("code")
        plan=result.get("planning_response")
        row={"submission_path": str(submission_path.relative_to(run)).replace("\\", "/"), **context(submission_path), "verdict": result.get("verdict"), "code_sha256": hashlib.sha256((code or "").encode()).hexdigest() if code else None, "selected_algorithm": selected_algorithm(plan), **features(code)}
        reference = references.get(row["problem_id"])
        if reference:
            left, right = set(row["signals"]), set(reference["signals"])
            row["reference_normalized_ast_match"] = row["normalized_ast_sha256"] == reference["normalized_ast_sha256"]
            row["reference_signal_jaccard"] = round(len(left & right) / len(left | right), 4) if left or right else 1.0
            row["reference_signals"] = reference["signals"]
        else:
            row["reference_normalized_ast_match"] = None; row["reference_signal_jaccard"] = None; row["reference_signals"] = []
        rows.append(row)
    by_problem=Counter(row["problem_id"] for row in rows); verdicts=Counter(row["verdict"] for row in rows)
    review_queue=[]
    for row in rows:
        if row["verdict"] == "AC" and not row["reference_normalized_ast_match"]:
            review_queue.append({key: row[key] for key in ("problem_id", "condition", "generation", "verdict", "code_sha256", "signals", "reference_signals", "reference_signal_jaccard", "selected_algorithm", "submission_path")})
    report={"schema_version":"1.1", "scope":"all judged Teacher and solver submissions; static evidence only", "submission_count":len(rows), "verdict_counts":dict(sorted(verdicts.items())), "unique_code_count":len({row["code_sha256"] for row in rows if row["code_sha256"]}), "problem_submission_counts":dict(sorted(by_problem.items(), key=lambda item: item[0] or "")), "reference_comparison":"normalized AST equality is clone detection only; signal overlap is not a correctness verdict", "nonreference_ac_review_queue":review_queue, "rows":rows}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"output":str(output),"submissions":len(rows),"unique_code":report["unique_code_count"],"verdict_counts":report["verdict_counts"]}))


if __name__ == "__main__": main()
