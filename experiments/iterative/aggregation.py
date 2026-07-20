from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any
import csv
from itertools import combinations
import json

from experiments.pilot.storage import write_json, write_text
def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def parse_lineage_manifests(run_dir: Path) -> list[dict[str, Any]]:
    """Parse every on-disk lineage manifest or fail before aggregation."""
    manifests: list[dict[str, Any]] = []
    for path in sorted((run_dir / "lineages").glob("*/lineage_manifest.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid lineage manifest: {path}") from error
        if not isinstance(value, dict) or not all(
                key in value for key in ("lineage_id", "condition", "problem_id")):
            raise ValueError(f"invalid lineage manifest schema: {path}")
        manifests.append(value)
    ids = [item["lineage_id"] for item in manifests]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate lineage_id in parsed lineage manifests")
    return manifests


def aggregate_run(
    lineages: list[dict[str, Any]], max_generations: int,
    configured_conditions: tuple[str, ...], *,
    parsed_lineage_manifests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not configured_conditions or len(set(configured_conditions)) != len(
            configured_conditions):
        raise ValueError("configured conditions must be nonempty and unique")
    manifests = parsed_lineage_manifests
    if manifests is not None:
        if len(lineages) != len(manifests):
            raise ValueError(
                "aggregate lineage count != valid parsed lineage manifests count")
        summary_ids = {item["lineage_id"] for item in lineages}
        manifest_ids = {item["lineage_id"] for item in manifests}
        if summary_ids != manifest_ids:
            raise ValueError("aggregate lineage identities differ from parsed manifests")
        observed_conditions = {item["condition"] for item in manifests}
    else:
        observed_conditions = {item["condition"] for item in lineages}
    if observed_conditions != set(configured_conditions):
        raise ValueError(
            "set(aggregate conditions) != set(configured conditions)")
    valid = [x for x in lineages if x.get("system_attempt_valid")]
    by_condition: dict[str, dict[str, Any]] = {}
    for condition in configured_conditions:
        rows = [x for x in valid if x["condition"] == condition]
        solved = [x for x in rows if x["outcome"] == "SOLVED"]
        curve = {
            f"success_within_{generation}_generations": _rate(
                sum(x.get("first_ac_generation") is not None and
                    x["first_ac_generation"] <= generation for x in rows), len(rows))
            for generation in range(1, max_generations + 1)
        }
        first = [x["first_ac_generation"] for x in solved]
        verdicts = Counter(
            (g["generation_index"], g["standardized_verdict"])
            for x in rows for g in x["generations"])
        transitions = Counter(
            (g.get("parent_verdict"), g["standardized_verdict"])
            for x in rows for g in x["generations"] if g.get("parent_verdict") is not None)
        edit_values = [g["normalized_code_edit_ratio"] for x in rows for g in x["generations"]
                       if g.get("normalized_code_edit_ratio") is not None]
        repeats = [g["exact_code_repeat"] for x in rows for g in x["generations"]
                   if g.get("exact_code_repeat") is not None]
        survival_lengths = []
        for lineage in rows:
            longest = current = 0
            previous_pair = None
            for generation in lineage["generations"]:
                pair = (generation.get("normalized_code_sha256"),
                        generation["standardized_verdict"])
                current = current + 1 if pair == previous_pair and pair[0] else 1
                longest = max(longest, current)
                previous_pair = pair
            survival_lengths.append(longest)
        by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_problem[row["problem_id"]].append(row)
        macro = mean(
            _rate(sum(x["outcome"] == "SOLVED" for x in group), len(group)) or 0
            for group in by_problem.values()) if by_problem else None
        total_tokens = sum(x["student_tokens"] + x["flat_ff_tokens"] for x in rows)
        per_problem_curves = {}
        for problem, group in by_problem.items():
            per_problem_curves[problem] = {
                str(generation): _rate(sum(
                    x.get("first_ac_generation") is not None and
                    x["first_ac_generation"] <= generation for x in group), len(group))
                for generation in range(1, max_generations + 1)}
        first_costs = []
        for lineage in solved:
            generations_to_ac = [g for g in lineage["generations"]
                                 if g["generation_index"] <= lineage["first_ac_generation"]]
            first_costs.append({
                "student_solver_calls": sum(g["planning_calls"] + g["final_calls"] for g in generations_to_ac),
                "total_model_calls": sum(g["planning_calls"] + g["final_calls"] + g["flat_ff_model_calls"] for g in generations_to_ac),
                "judge_submissions": sum(g["judge_submissions"] for g in generations_to_ac),
                "student_tokens": sum(g["student_total_tokens"] for g in generations_to_ac),
                "total_tokens": sum(g["student_total_tokens"] + g["flat_ff_total_tokens"] for g in generations_to_ac),
            })
        def average_cost(field):
            return mean(x[field] for x in first_costs) if first_costs else None
        by_condition[condition] = {
            "lineages": len(rows), "solved": len(solved),
            "micro_success_rate": _rate(len(solved), len(rows)),
            "problem_macro_success_rate": macro,
            "per_problem_cumulative_success": per_problem_curves,
            **curve,
            "mean_generations_to_first_ac": mean(first) if first else None,
            "median_generations_to_first_ac": median(first) if first else None,
            "completed_unsolved_rate": _rate(sum(x["outcome"] == "COMPLETED_UNSOLVED" for x in rows), len(rows)),
            "protocol_termination_rate": _rate(sum(x["outcome"].startswith("TERMINATED_") for x in rows), len(rows)),
            "student_solver_calls": sum(x["solver_calls"] for x in rows),
            "flat_ff_generation_calls": sum(x["flat_ff_model_calls"] for x in rows),
            "total_model_calls": sum(x["solver_calls"] + x["flat_ff_model_calls"] for x in rows),
            "judge_submissions": sum(x["judge_submissions"] for x in rows),
            "student_tokens": sum(x["student_tokens"] for x in rows),
            "flat_ff_tokens": sum(x["flat_ff_tokens"] for x in rows),
            "total_tokens": total_tokens,
            "token_cost_per_solved_lineage": total_tokens / len(solved) if solved else None,
            "mean_student_solver_calls_to_first_ac": average_cost("student_solver_calls"),
            "mean_total_model_calls_to_first_ac": average_cost("total_model_calls"),
            "mean_judge_submissions_to_first_ac": average_cost("judge_submissions"),
            "mean_student_tokens_to_first_ac": average_cost("student_tokens"),
            "mean_total_tokens_to_first_ac": average_cost("total_tokens"),
            "new_breakthroughs_by_generation": {
                str(generation): sum(x.get("first_ac_generation") == generation for x in rows)
                for generation in range(1, max_generations + 1)},
            "verdict_by_generation": {f"g{g}:{v}": n for (g, v), n in sorted(verdicts.items())},
            "verdict_transition_matrix": {f"{a}->{b}": n for (a, b), n in sorted(transitions.items())},
            "mean_parent_child_normalized_code_edit_ratio": mean(edit_values) if edit_values else None,
            "parent_child_exact_code_repeat_rate": _rate(sum(repeats), len(repeats)),
            "mean_same_error_code_survival_generations": (
                mean(survival_lengths) if survival_lengths else None),
            "max_same_error_code_survival_generations": (
                max(survival_lengths) if survival_lengths else None),
            "code_extraction_failure_rate": _rate(sum(not g["final_code_extracted"] for x in rows for g in x["generations"]), sum(len(x["generations"]) for x in rows)),
            "code_extraction_failure_rate_by_generation": {
                str(generation): _rate(
                    sum(not g["final_code_extracted"] for x in rows for g in x["generations"]
                        if g["generation_index"] == generation),
                    sum(1 for x in rows for g in x["generations"]
                        if g["generation_index"] == generation))
                for generation in range(1, max_generations + 1)},
            "flat_ff_protocol_failure_rate": _rate(sum(x["outcome"] == "TERMINATED_FLAT_FF_PROTOCOL_FAILURE" for x in rows), len(rows)),
            "flat_ff_protocol_failures_by_generation": {
                str(generation): sum(
                    x["outcome"] == "TERMINATED_FLAT_FF_PROTOCOL_FAILURE" and
                    x["generations"] and x["generations"][-1]["generation_index"] == generation
                    for x in rows)
                for generation in range(1, max_generations + 1)},
        }
    clusters: dict[tuple[str, int], dict[str, bool]] = defaultdict(dict)
    for row in valid:
        clusters[(row["root_episode_id"], row["lineage_repeat_index"])][row["condition"]] = row["outcome"] == "SOLVED"
    pairwise = {}
    for left, right in combinations(configured_conditions, 2):
        paired = [values for values in clusters.values() if left in values and right in values]
        pairwise[f"{left}_vs_{right}"] = {
            "pairs": len(paired), "left_only_solved": sum(v[left] and not v[right] for v in paired),
            "right_only_solved": sum(v[right] and not v[left] for v in paired),
            "both_solved": sum(v[right] and v[left] for v in paired),
            "neither_solved": sum(not v[right] and not v[left] for v in paired),
        }
    result = {
        "schema_version": "1.0", "experiment_policy": "minimal_failure_lineage_v1",
        "lineages_total": len(lineages),
        "valid_parsed_lineage_manifests": (
            len(manifests) if manifests is not None else None),
        "configured_conditions": list(configured_conditions),
        "system_attempt_valid": len(valid),
        "infrastructure_failure_rate": _rate(sum(x["outcome"] == "INVALID_INFRASTRUCTURE" for x in lineages), len(lineages)),
        "conditions": by_condition, "pairwise_lineage_outcomes": pairwise,
        "three_condition_union_coverage": _rate(sum(any(v.values()) for v in clusters.values()), len(clusters)),
        "scientific_guardrails": [
            "A later-generation AC is not evidence of model-weight or base-capability growth.",
            "Benefits may arise from external memory, search, iteration, or repeated sampling.",
            "Only an increment over equal-opportunity independent restarts supports cumulative value from minimal failure inheritance.",
            "Only an increment of the Flat-FF chain over the code-and-verdict chain supports incremental Flat-FF value.",
            "Flat-FF regressions may reflect anchoring, accumulated error, context burden, or protocol failure.",
            "Lineages sharing a problem/root are clustered observations, not independent problems.",
        ],
    }
    if set(result["conditions"]) != set(configured_conditions):
        raise AssertionError(
            "set(aggregate conditions) != set(configured conditions)")
    if manifests is not None and result["lineages_total"] != len(manifests):
        raise AssertionError(
            "aggregate lineage count != valid parsed lineage manifests count")
    return result


def transition_rows(lineages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for lineage in lineages:
        cumulative_solver = cumulative_model = cumulative_tokens = 0
        for generation in lineage.get("generations", []):
            cumulative_solver += generation["planning_calls"] + generation["final_calls"]
            cumulative_model += generation["planning_calls"] + generation["final_calls"] + generation["flat_ff_model_calls"]
            cumulative_tokens += generation["student_total_tokens"] + generation["flat_ff_total_tokens"]
            rows.append({
                "problem": lineage["problem_id"], "root": lineage["root_episode_id"],
                "condition": lineage["condition"], "lineage_repeat": lineage["lineage_repeat_index"],
                "generation": generation["generation_index"], "parent_verdict": generation.get("parent_verdict"),
                "child_verdict": generation["standardized_verdict"],
                "parent_code_hash": generation.get("parent_code_sha256"),
                "child_code_hash": generation.get("code_sha256"),
                "edit_ratio": generation.get("normalized_code_edit_ratio"),
                "parent_flat_ff_hash": generation.get("parent_flat_ff_sha256"),
                "solved": generation["standardized_verdict"] == "AC",
                "terminated_reason": lineage["outcome"] if generation is lineage["generations"][-1] else None,
                "cumulative_solver_calls": cumulative_solver,
                "cumulative_total_model_calls": cumulative_model,
                "cumulative_tokens": cumulative_tokens,
            })
    return rows


def write_reports(run_dir: Path, lineages: list[dict[str, Any]], aggregate: dict[str, Any]) -> None:
    write_json(run_dir / "aggregate.json", aggregate)
    write_json(run_dir / "lineages.json", lineages)
    rows = transition_rows(lineages)
    fields = list(rows[0]) if rows else ["problem", "root", "condition", "lineage_repeat", "generation"]
    for name, data in (("lineage_transitions.csv", rows),):
        path = run_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(data)
    lineage_fields = ["lineage_id", "problem_id", "root_episode_id", "condition",
                      "lineage_repeat_index", "outcome", "first_ac_generation",
                      "generations_attempted", "solver_calls", "flat_ff_model_calls",
                      "judge_submissions", "student_tokens", "flat_ff_tokens"]
    with (run_dir / "lineage_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=lineage_fields)
        writer.writeheader(); writer.writerows({k: x.get(k) for k in lineage_fields} for x in lineages)
    lines = ["# Minimal Failure Lineage Report", "", "This is an opportunity-balanced, not token- or call-balanced, comparison.", ""]
    for condition, metrics in aggregate["conditions"].items():
        lines += [f"## {condition}", "", f"- Valid lineages: {metrics['lineages']}",
                  f"- Solved: {metrics['solved']}", f"- Micro success: {metrics['micro_success_rate']}", ""]
    lines += ["## Scientific interpretation boundary", ""] + [f"- {x}" for x in aggregate["scientific_guardrails"]]
    write_text(run_dir / "aggregate.md", "\n".join(lines) + "\n")
