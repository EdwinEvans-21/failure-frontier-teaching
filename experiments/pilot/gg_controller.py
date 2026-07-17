from __future__ import annotations

from typing import Any
import json
import math
import re


GG_GENERATION_POLICY = "blueprint_render_v1"
BLUEPRINT_POLICY = "compact_blueprint_v1"
BLUEPRINT_FIELDS = {
    "constraints": (2, 4, ("point", "importance")),
    "approaches": (
        1,
        2,
        ("name", "core_idea", "why_plausible", "main_risk"),
    ),
    "correctness": (2, 4, ("claim", "check")),
    "implementation": (3, 6, ("risk", "check")),
}


def validate_blueprint_response(
    content: str,
    finish_reason: str,
) -> dict[str, Any]:
    errors: list[str] = []
    forbidden: list[str] = []
    blueprint: dict[str, Any] | None = None

    status = (
        "BLUEPRINT_TRUNCATED"
        if finish_reason == "length" else "BLUEPRINT_INVALID_JSON"
    )
    if finish_reason == "length":
        errors.append("finish_reason_length")

    if "```" in content:
        forbidden.append("code_fence")
    if re.search(
        r"(?m)^\s*(?:class\s+Solution\b|def\s+\w+\s*\(|from\s+\w+\s+import\s+|import\s+\w+\s*$)",
        content,
    ):
        forbidden.append("solution_code")
    if forbidden:
        errors.extend(f"forbidden_{item}" for item in forbidden)
        if finish_reason != "length":
            status = "BLUEPRINT_FORBIDDEN_CONTENT"

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = None
        if finish_reason != "length" and not forbidden:
            errors.append("invalid_json")
    if isinstance(parsed, dict):
        blueprint = parsed
        if set(parsed) != set(BLUEPRINT_FIELDS):
            errors.append("top_level_categories_invalid")
        for category, (minimum, maximum, fields) in BLUEPRINT_FIELDS.items():
            items = parsed.get(category)
            if not isinstance(items, list):
                errors.append(f"{category}_must_be_array")
                continue
            if not minimum <= len(items) <= maximum:
                errors.append(f"{category}_item_count_invalid")
            for index, item in enumerate(items):
                if not isinstance(item, dict) or set(item) != set(fields):
                    errors.append(f"{category}_{index}_schema_invalid")
                    continue
                for field in fields:
                    value = item.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{category}_{index}_{field}_empty")
                    elif len(value) > 400 or "\n" in value:
                        errors.append(f"{category}_{index}_{field}_not_compact")
        parsed_text = "\n".join(_blueprint_strings(parsed))
        if re.search(r"\bclass\s+Solution\b|\bdef\s+\w+\s*\(", parsed_text):
            forbidden.append("solution_code")
            errors.append("forbidden_solution_code")
    elif parsed is not None:
        errors.append("blueprint_must_be_object")

    if finish_reason not in {"stop", "length"}:
        errors.append("finish_reason_not_stop")
    if finish_reason == "stop" and forbidden:
        status = "BLUEPRINT_FORBIDDEN_CONTENT"
    elif finish_reason == "stop" and not errors:
        status = "BLUEPRINT_VALID"
    elif finish_reason == "stop" and parsed is not None:
        status = "BLUEPRINT_INVALID_SCHEMA"

    return {
        "status": status,
        "valid": status == "BLUEPRINT_VALID",
        "blueprint": blueprint,
        "errors": _unique(errors),
        "forbidden_content": _unique(forbidden),
        "finish_reason": finish_reason,
        "schema_policy": BLUEPRINT_POLICY,
    }


def material_section_budgets(target_tokens: int) -> dict[str, int]:
    constraints = math.floor(target_tokens * 0.15 + 0.5)
    approaches = math.floor(target_tokens * 0.45 + 0.5)
    correctness = math.floor(target_tokens * 0.20 + 0.5)
    implementation = target_tokens - constraints - approaches - correctness
    return {
        "constraints": constraints,
        "approaches": approaches,
        "correctness": correctness,
        "implementation": implementation,
    }


def material_paragraph_budgets(target_tokens: int) -> dict[str, Any]:
    paragraphs = 2 if target_tokens <= 1600 else 3 if target_tokens <= 3500 else 4
    return {
        "max_paragraphs_per_section": paragraphs,
        "max_sentences_per_paragraph": 4,
        "sections": {
            name: paragraphs
            for name in (
                "constraints",
                "approaches",
                "correctness",
                "implementation",
            )
        },
    }


def scaled_section_budgets(
    target_tokens: int,
    observed_tokens: int | None,
) -> tuple[dict[str, int], float]:
    scale = 1.0
    if observed_tokens and observed_tokens > 0 and observed_tokens < target_tokens:
        scale = min(1.5, target_tokens / observed_tokens)
    base = material_section_budgets(target_tokens)
    return ({key: math.ceil(value * scale) for key, value in base.items()}, scale)


def select_material_fallback(
    records: list[dict[str, Any]],
    target_tokens: int,
    lower_bound: int,
    upper_bound: int,
) -> dict[str, Any] | None:
    candidates = [
        item for item in records
        if item.get("finish_reason") == "stop"
        and item.get("semantic_completeness_passed") is True
        and not item.get("forbidden_content")
        and item.get("state")
        not in {"TRUNCATED_TOO_LONG", "INVALID_CONTENT", "FORBIDDEN_CONTENT"}
    ]
    return min(
        candidates,
        key=lambda item: (
            _interval_distance(item["completion_tokens"], lower_bound, upper_bound),
            abs(item["completion_tokens"] - target_tokens),
            0 if item["completion_tokens"] >= target_tokens else 1,
            item["version"],
        ),
        default=None,
    )


def duplicate_material_request(
    records: list[dict[str, Any]],
    *,
    prompt_hash: str,
    max_output_tokens: int,
    source_material_version: int | None,
    operation: str,
) -> bool:
    if not records:
        return False
    previous = records[-1]
    signature = (
        prompt_hash,
        max_output_tokens,
        source_material_version,
        operation,
    )
    return (
        previous.get("prompt_hash"),
        previous.get("request_max_tokens"),
        previous.get("source_material_version"),
        previous.get("operation"),
    ) == signature


def _interval_distance(tokens: int, lower_bound: int, upper_bound: int) -> int:
    if tokens < lower_bound:
        return lower_bound - tokens
    if tokens > upper_bound:
        return tokens - upper_bound
    return 0


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _blueprint_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _blueprint_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _blueprint_strings(item)]
    return []
