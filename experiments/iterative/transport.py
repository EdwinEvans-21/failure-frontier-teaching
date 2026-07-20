from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import time
import urllib.request


class SanitizedTransportTracker:
    """Record physical HTTP attempts without persisting headers or bodies."""

    def __init__(self, artifact: str | Path) -> None:
        self.artifact = Path(artifact)
        self.context: dict[str, Any] = {}
        self.attempts = 0

    def bind(self, request: dict[str, Any]) -> None:
        self.context = {
            "role": request.get("role"),
            "problem_id": request.get("problem_id"),
            "condition": request.get("condition"),
        }

    def __call__(self, request, *, timeout):
        self.attempts += 1
        started = time.monotonic()
        record = {
            "attempt": self.attempts,
            **self.context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.get_method(),
            "url": request.full_url,
            "timeout_seconds": timeout,
            "request_headers_persisted": False,
            "request_body_persisted": False,
        }
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
            record.update({
                "outcome": "response_opened",
                "status_code": int(getattr(response, "status", 200)),
            })
            return response
        except Exception as error:
            record.update({"outcome": "transport_error",
                           "error_category": type(error).__name__})
            raise
        finally:
            record["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            self.artifact.parent.mkdir(parents=True, exist_ok=True)
            with self.artifact.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class TrackedModelClient:
    def __init__(self, client: Any, tracker: SanitizedTransportTracker) -> None:
        self.client = client
        self.tracker = tracker

    def complete(self, **request):
        self.tracker.bind(request)
        return self.client.complete(**request)
