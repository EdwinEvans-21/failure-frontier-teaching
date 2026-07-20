from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


INHERITANCE_HEADER = """A previous solver submitted the code below for this problem and received the standardized verdict shown below.

The verdict establishes only that this submitted program did not pass the evaluator. It does not by itself prove that the algorithm family, intended invariant, or every part of the code is wrong.

Use the public problem statement, the submitted code, and the verdict as reference. Diagnose the failure independently and construct your own correct and efficient solution.

Do not produce a criticism report. Do not merely patch the previous code unless its underlying approach is justified. You may retain, modify, or replace the approach.

Produce one complete final solution using the shared output format."""


@dataclass(frozen=True)
class ParentMaterial:
    generation: int
    code: str
    verdict: str
    code_sha256: str
    flat_ff: str | None = None
    flat_ff_sha256: str | None = None
    flat_renderer_version: str | None = None
    validated_record_path: str | None = None
    validated_record_sha256: str | None = None
    flat_addon: str | None = None
    flat_addon_path: str | None = None
    flat_addon_sha256: str | None = None
    flat_addon_renderer_version: str | None = None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_code_hash(code: str) -> str:
    normalized = "\n".join(line.rstrip() for line in code.strip().splitlines()) + "\n"
    return sha256_text(normalized)


def render_inherited_payload(parent: ParentMaterial, *, include_flat: bool) -> str:
    blocks = [
        INHERITANCE_HEADER,
        "# Previous Submitted Code\n\n```python\n" + parent.code.rstrip() + "\n```",
        "# Standardized Verdict\n\n" + parent.verdict,
    ]
    if include_flat:
        if not parent.flat_ff or not parent.flat_ff_sha256:
            raise ValueError("Flat FF condition requires a verified direct-parent Flat FF")
        blocks.append("# Direct-Parent Flat Failure Frontier\n\n" + parent.flat_ff.rstrip())
    return "\n\n".join(blocks) + "\n"


def render_inherited_payload_v2(parent: ParentMaterial) -> str:
    base = render_inherited_payload(parent, include_flat=False).rstrip()
    if not all((parent.validated_record_path, parent.validated_record_sha256,
                parent.flat_addon, parent.flat_addon_path,
                parent.flat_addon_sha256, parent.flat_addon_renderer_version)):
        raise ValueError("Flat-v2 condition requires a verified direct-parent add-on")
    payload = (
        base + "\n\n# Direct-Parent Flat Failure Analysis\n\n"
        + parent.flat_addon.rstrip() + "\n"
    )
    if parent.code and payload.count(parent.code) != 1:
        raise ValueError("Flat-v2 payload must contain complete parent code exactly once")
    return payload


def audit_direct_parent_payload(
    payload: str, parent: ParentMaterial, ancestors: list[ParentMaterial]
) -> list[str]:
    """Check direct-parent lineage isolation without interpreting prose.

    Natural-language phrases are deliberately not scanned.  Text such as
    "expected output" can be a harmless statement about the trust boundary.
    Hidden evaluation data is rejected by ``audit_structured_parent_sources``
    at its structured source boundary instead.
    """
    issues: list[str] = []
    for ancestor in ancestors:
        if ancestor.generation == parent.generation:
            continue
        for label, value in (("code", ancestor.code), ("flat_ff", ancestor.flat_ff),
                             ("flat_addon", ancestor.flat_addon)):
            parent_value = {
                "code": parent.code, "flat_ff": parent.flat_ff,
                "flat_addon": parent.flat_addon,
            }[label]
            if value and value != parent_value and value in payload:
                issues.append(f"grandparent_{label}_present")
        if (ancestor.verdict != parent.verdict and
                f"# Standardized Verdict\n\n{ancestor.verdict}" in payload):
            issues.append("grandparent_verdict_present")
    return sorted(set(issues))


_PRIVATE_JUDGE_KEYS = {
    "judge_internal", "judge_diagnostics", "private_diagnostics",
    "traceback", "stack_trace", "stdout", "stderr", "exit_code",
    "failed_case", "failed_case_index", "test_case_index", "case_index",
    "hidden_test_id", "hidden_case_id", "hidden_test_index",
    "hidden_test_count", "hidden_case_count", "total_hidden_tests",
    "passed_hidden_tests", "expected", "expected_value", "expected_output",
    "actual", "actual_value", "actual_output", "hidden_input",
}


def _normalized_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def audit_structured_parent_sources(parent: ParentMaterial) -> list[str]:
    """Fail closed only on structured private-evaluation fields.

    The validated FF record is the only structured analysis source inherited
    by Flat-v2.  Model-authored string values are intentionally opaque here;
    provenance/schema validation owns their meaning.  Field names, however,
    reveal whether private Judge data was structurally attached.
    """
    if not parent.validated_record_path:
        return []
    path = Path(parent.validated_record_path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["structured_source_unreadable"]
    issues: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            keys = {_normalized_key(key) for key in value}
            private = keys & _PRIVATE_JUDGE_KEYS
            if private:
                issues.update(f"private_structured_field:{key}" for key in private)
            if ({"input", "actual"} <= keys or
                    {"hidden_input", "actual_output"} <= keys):
                issues.add("hidden_input_actual_pair")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(record)
    return sorted(issues)
