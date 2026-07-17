from __future__ import annotations

from dataclasses import dataclass
import ast
import re


PYTHON_BLOCK = re.compile(r"```python[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
ANY_BLOCK = re.compile(r"```[^\n]*\r?\n.*?```", re.DOTALL)


@dataclass(frozen=True)
class ExtractionResult:
    ok: bool
    code: str | None
    error: str | None


def extract_single_python_code(response: str, *, truncated: bool = False,
                               allow_complete_when_truncated: bool = False) -> ExtractionResult:
    if truncated and not allow_complete_when_truncated:
        return ExtractionResult(False, None, "response_truncated")
    matches = PYTHON_BLOCK.findall(response)
    if len(matches) != 1:
        reason = "missing_python_code_block" if not matches else "multiple_python_code_blocks"
        return ExtractionResult(False, None, reason)
    if len(ANY_BLOCK.findall(response)) != 1:
        return ExtractionResult(False, None, "ambiguous_code_blocks")
    code = matches[0].strip()
    if not code:
        return ExtractionResult(False, None, "empty_python_code_block")
    return ExtractionResult(True, code + "\n", None)


def extract_raw_python_code(response: str) -> ExtractionResult:
    code = response.strip()
    if not code:
        return ExtractionResult(False, None, "empty_python_source")
    if "```" in code or re.search(r"(?m)^#{1,6}\s", code):
        return ExtractionResult(False, None, "markdown_not_allowed")
    try:
        ast.parse(code)
    except SyntaxError:
        return ExtractionResult(False, None, "invalid_python_source")
    return ExtractionResult(True, code + "\n", None)
