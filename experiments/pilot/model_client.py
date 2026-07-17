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

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.api_key = os.environ.get(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"missing API key environment variable: {config.api_key_env}")
        if config.model_name == "RESEARCHER_TO_SET":
            raise ValueError("configure the provider's actual non-reasoning model name")
        self._tokenizer: Any | None = None

    def complete(self, **request: str) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": request["system_prompt"]},
                {"role": "user", "content": request["user_prompt"]},
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_output_tokens,
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: BaseException | None = None
        for attempt in range(self.config.network_retry_limit + 1):
            started = time.monotonic()
            http_request = urllib.request.Request(
                self.config.base_url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(http_request, timeout=180) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                choice = raw["choices"][0]
                usage = raw.get("usage", {})
                output_tokens = _optional_int(usage.get("completion_tokens"))
                token_count_source = "api_usage"
                if output_tokens is None:
                    output_tokens = self._fallback_token_count(choice["message"]["content"])
                    token_count_source = "configured_model_tokenizer"
                return ModelResponse(
                    content=choice["message"]["content"],
                    input_tokens=_optional_int(usage.get("prompt_tokens")),
                    output_tokens=output_tokens,
                    finish_reason=choice.get("finish_reason"),
                    request_id=raw.get("id"),
                    seed=self.config.seed,
                    seed_supported=None,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    token_count_source=token_count_source,
                )
            except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                    TypeError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self.config.network_retry_limit:
                    time.sleep(self.config.network_retry_backoff_seconds * (2 ** attempt))
        raise ModelInfrastructureError("model API request failed after infrastructure retries") from last_error

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
