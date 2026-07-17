from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import platform

from .config import PilotConfig
from .model_client import (
    CLIENT_VERSION,
    ApiRequestError,
    DeepSeekCompatibleClient,
)
from .storage import write_json, write_text


EXPECTED_TEXT = "DEEPSEEK_API_COMPATIBILITY_OK"
CHECK_MESSAGE = (
    "Return exactly the following text and nothing else:\n\n" + EXPECTED_TEXT
)


def run_api_compatibility_check(
    config: PilotConfig,
    client: DeepSeekCompatibleClient,
    output_root: str | Path,
    *,
    project_root: str | Path = ".",
    timestamp: str | None = None,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    project = Path(project_root).resolve()
    if root == project or root.is_relative_to(project):
        raise ValueError("api-check output-root must be outside the repository")
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact_dir = root / "api-check" / timestamp
    artifact_dir.mkdir(parents=True, exist_ok=False)
    called_at = datetime.now(timezone.utc).isoformat()
    payload = client.build_chat_payload([
        {"role": "user", "content": CHECK_MESSAGE},
    ])
    request_record = {
        "api_base_url": config.model.base_url,
        "endpoint": client.endpoint,
        "requested_model": payload["model"],
        "thinking": payload["thinking"],
        "temperature": payload["temperature"],
        "top_p": payload["top_p"],
        "max_tokens": payload["max_tokens"],
        "stream": payload["stream"],
        "messages": payload["messages"],
        "called_at": called_at,
        "client_version": CLIENT_VERSION,
        "python_version": platform.python_version(),
        "seed": None,
        "seed_supported": False,
        "authorization_source": config.model.api_key_env,
    }
    request_path = artifact_dir / "request.json"
    response_path = artifact_dir / "response.json"
    result_path = artifact_dir / "result.json"
    write_json(request_path, request_record)
    try:
        transport = client.send_chat(payload, retry=False)
    except ApiRequestError as error:
        write_json(response_path, {
            "http_status": error.status_code,
            "error": error.response_body,
        })
        result = {
            "passed": False,
            "failure_reasons": ["http_or_api_call_failed"],
            "http_status": error.status_code,
            "requested_model": config.model.model_name,
            "raw_response_artifact_path": str(response_path),
            "request_id": None,
            "request_id_supported": False,
            "judge_accessed": False,
            "formal_pilot_data_generated": False,
        }
        _finish(artifact_dir, result_path, result)
        return result

    raw = transport.data
    write_json(response_path, raw)
    parsed, failures = _parse_and_validate(raw, transport.headers, payload)
    result = {
        "passed": not failures,
        "failure_reasons": failures,
        "http_status": transport.status_code,
        "latency_ms": transport.latency_ms,
        "requested_model": config.model.model_name,
        **parsed,
        "raw_response_artifact_path": str(response_path),
        "request_artifact_path": str(request_path),
        "judge_accessed": False,
        "formal_pilot_data_generated": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    _finish(artifact_dir, result_path, result)
    return result


def _parse_and_validate(
    raw: dict[str, Any], headers: dict[str, str], payload: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    choices = raw.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    message = choice.get("message") if isinstance(choice, dict) else {}
    message = message if isinstance(message, dict) else {}
    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    content = message.get("content")
    reasoning_content = message.get("reasoning_content")
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    request_id = _header_request_id(headers)
    if not isinstance(content, str) or not content.strip():
        failures.append("content_missing_or_empty")
    elif EXPECTED_TEXT not in content:
        failures.append("expected_text_missing")
    if not isinstance(finish_reason, str) or not finish_reason:
        failures.append("finish_reason_missing")
    if not _nonnegative_int(prompt_tokens):
        failures.append("prompt_tokens_missing_or_invalid")
    if not _positive_int(completion_tokens):
        failures.append("completion_tokens_missing_or_invalid")
    if not _positive_int(total_tokens):
        failures.append("total_tokens_missing_or_invalid")
    if reasoning_content not in (None, ""):
        failures.append("reasoning_content_not_empty")
    if payload.get("thinking") != {"type": "disabled"}:
        failures.append("thinking_not_explicitly_disabled")
    return {
        "response_id": raw.get("id"),
        "returned_model": raw.get("model"),
        "finish_reason": finish_reason,
        "content": content,
        "reasoning_content": reasoning_content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "request_id": request_id,
        "request_id_supported": request_id is not None,
        "seed": None,
        "seed_supported": False,
    }, failures


def _header_request_id(headers: dict[str, str]) -> str | None:
    normalized = {key.lower(): value for key, value in headers.items()}
    for name in ("x-request-id", "request-id", "cf-ray"):
        if normalized.get(name):
            return normalized[name]
    return None


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _finish(artifact_dir: Path, result_path: Path, result: dict[str, Any]) -> None:
    write_json(result_path, result)
    status = "PASS" if result["passed"] else "FAIL"
    lines = [
        "# DeepSeek API Compatibility Check",
        "",
        f"- Status: {status}",
        f"- Requested model: {result.get('requested_model')}",
        f"- Returned model: {result.get('returned_model')}",
        f"- Finish reason: {result.get('finish_reason')}",
        f"- Reasoning content empty: {result.get('reasoning_content') in (None, '')}",
        f"- Failure reasons: {result.get('failure_reasons', [])}",
        "- Judge accessed: false",
        "- Formal Pilot data generated: false",
    ]
    write_text(artifact_dir / "summary.md", "\n".join(lines) + "\n")
