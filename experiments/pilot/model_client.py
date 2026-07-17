from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os
import time
import urllib.error
import urllib.request

from .config import ModelConfig


class ModelInfrastructureError(RuntimeError):
    pass


CLIENT_VERSION = "fft-urllib-deepseek/1"


class ApiRequestError(ModelInfrastructureError):
    def __init__(self, message: str, *, status_code: int | None = None,
                 response_body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass(frozen=True)
class ApiTransportResponse:
    data: dict[str, Any]
    headers: dict[str, str]
    status_code: int
    latency_ms: int


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None
    request_id: str | None
    seed: int | None
    seed_supported: bool | None
    latency_ms: int
    token_count_source: str

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class ModelClient(Protocol):
    def complete(
        self,
        *,
        role: str,
        problem_id: str,
        condition: str,
        system_prompt: str,
        user_prompt: str,
    ) -> ModelResponse: ...


class DeepSeekCompatibleClient:
    """Minimal OpenAI-compatible client with infrastructure-only retries."""

    def __init__(self, config: ModelConfig, *, opener: Any = None) -> None:
        self.config = config
        self.api_key = os.environ.get(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"missing API key environment variable: {config.api_key_env}")
        if config.model_name == "RESEARCHER_TO_SET":
            raise ValueError("configure the provider's actual non-reasoning model name")
        self._tokenizer: Any | None = None
        self._opener = opener or urllib.request.urlopen

    @property
    def endpoint(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def build_chat_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
            "thinking": dict(self.config.thinking or {}),
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        return payload

    def complete(self, **request: str) -> ModelResponse:
        payload = self.build_chat_payload([
                {"role": "system", "content": request["system_prompt"]},
                {"role": "user", "content": request["user_prompt"]},
        ])
        transport = self.send_chat(payload, retry=True)
        raw = transport.data
        try:
            choice = raw["choices"][0]
            usage = raw.get("usage", {})
            output_tokens = _optional_int(usage.get("completion_tokens"))
            token_count_source = "api_usage"
            if output_tokens is None:
                output_tokens = self._fallback_token_count(choice["message"]["content"])
                token_count_source = "configured_model_tokenizer"
            request_id = _request_id(transport.headers)
            return ModelResponse(
                content=choice["message"]["content"],
                input_tokens=_optional_int(usage.get("prompt_tokens")),
                output_tokens=output_tokens,
                finish_reason=choice.get("finish_reason"),
                request_id=request_id,
                seed=self.config.seed,
                seed_supported=False,
                latency_ms=transport.latency_ms,
                token_count_source=token_count_source,
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ModelInfrastructureError("model API response schema is unsupported") from error

    def send_chat(self, payload: dict[str, Any], *, retry: bool) -> ApiTransportResponse:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: BaseException | None = None
        attempts = self.config.network_retry_limit + 1 if retry else 1
        for attempt in range(attempts):
            started = time.monotonic()
            http_request = urllib.request.Request(
                self.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with self._opener(http_request, timeout=180) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    status_code = int(getattr(response, "status", 200))
                if not isinstance(raw, dict):
                    raise ValueError("response must be an object")
                return ApiTransportResponse(
                    data=raw,
                    headers=headers,
                    status_code=status_code,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            except urllib.error.HTTPError as error:
                response_body = _decode_error_body(error.read())
                raise ApiRequestError(
                    f"model API returned HTTP {error.code}",
                    status_code=error.code,
                    response_body=response_body,
                ) from error
            except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                    TypeError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt + 1 < attempts:
                    time.sleep(self.config.network_retry_backoff_seconds * (2 ** attempt))
        raise ApiRequestError("model API request failed after infrastructure retries") from last_error

    def _fallback_token_count(self, content: str) -> int:
        name = self.config.tokenizer_name
        if not name or name == "RESEARCHER_TO_SET":
            raise ModelInfrastructureError(
                "API omitted completion_tokens and no matching tokenizer is configured"
            )
        try:
            from transformers import AutoTokenizer  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelInfrastructureError(
                "transformers is required for the configured tokenizer fallback"
            ) from error
        if self._tokenizer is None:
            self._tokenizer = AutoTokenizer.from_pretrained(
                name,
                revision=self.config.tokenizer_revision,
                trust_remote_code=False,
            )
        return len(self._tokenizer.encode(content, add_special_tokens=False))


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _request_id(headers: dict[str, str]) -> str | None:
    for name in ("x-request-id", "request-id", "cf-ray"):
        value = headers.get(name)
        if value:
            return value
    return None


def _decode_error_body(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"unparsed_body": body.decode("utf-8", errors="replace")}


class MockModelClient:
    """Deterministic scripted model used to exercise the complete pilot chain."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.calls: list[dict[str, str]] = []
        self._responses: dict[str, list[dict[str, Any]]] = {}
        if config.mock_responses_path:
            loaded = json.loads(Path(config.mock_responses_path).read_text(encoding="utf-8"))
            self._responses = {key: list(value) for key, value in loaded.items()}

    @staticmethod
    def key(role: str, problem_id: str, condition: str) -> str:
        return f"{role}|{problem_id}|{condition}"

    def complete(self, **request: str) -> ModelResponse:
        self.calls.append(dict(request))
        key = self.key(request["role"], request["problem_id"], request["condition"])
        scripted = self._responses.get(key, [])
        item = scripted.pop(0) if scripted else self._default(request["role"])
        return ModelResponse(
            content=item["content"],
            input_tokens=item.get("input_tokens", 100),
            output_tokens=item.get("output_tokens", 64),
            finish_reason=item.get("finish_reason", "stop"),
            request_id=item.get("request_id", f"mock-{len(self.calls)}"),
            seed=self.config.seed,
            seed_supported=True,
            latency_ms=item.get("latency_ms", 0),
            token_count_source=item.get("token_count_source", "mock_usage"),
        )

    @staticmethod
    def _default(role: str) -> dict[str, Any]:
        if role in {"teacher", "student"}:
            content = "## Approach\nMock submission.\n\n## Code\n```python\nclass Solution:\n    pass\n```"
        else:
            content = "## Core Insight\nDeterministic mock teaching material."
        return {"content": content, "output_tokens": 64}
