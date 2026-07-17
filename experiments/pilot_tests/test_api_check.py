from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import json
import os
import tempfile
import unittest

from experiments.pilot.api_check import (
    EXPECTED_TEXT,
    run_api_compatibility_check,
)
from experiments.pilot.config import load_config
from experiments.pilot.model_client import DeepSeekCompatibleClient


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "experiments" / "configs" / "pilot_v1.yaml"
SECRET = "unit-test-secret-must-not-be-persisted"


class FakeHttpResponse:
    def __init__(self, payload, headers=None, status=200):
        self.payload = payload
        self.headers = headers or {}
        self.status = status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CapturingOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append({
            "url": request.full_url,
            "payload": json.loads(request.data.decode("utf-8")),
            "authorization": request.get_header("Authorization"),
            "timeout": timeout,
        })
        return self.response


def response_payload(*, reasoning_content=None, completion_tokens=7):
    usage = {"prompt_tokens": 15, "total_tokens": 22}
    if completion_tokens is not None:
        usage["completion_tokens"] = completion_tokens
    return {
        "id": "response-123",
        "model": "deepseek-v4-flash",
        "choices": [{
            "finish_reason": "stop",
            "message": {
                "content": EXPECTED_TEXT,
                "reasoning_content": reasoning_content,
            },
        }],
        "usage": usage,
    }


class ApiCompatibilityCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_root = Path(self.temporary.name)
        self.config = replace(load_config(CONFIG), mode="api-check")

    def run_check(self, payload, headers=None):
        opener = CapturingOpener(FakeHttpResponse(payload, headers=headers))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": SECRET}):
            client = DeepSeekCompatibleClient(self.config.model, opener=opener)
            result = run_api_compatibility_check(
                self.config,
                client,
                self.output_root,
                project_root=ROOT,
                timestamp="fixed",
            )
        return result, opener

    def test_success_parses_usage_disables_thinking_and_persists_no_key(self):
        result, opener = self.run_check(
            response_payload(), headers={"x-request-id": "request-456"})
        self.assertTrue(result["passed"])
        self.assertEqual(len(opener.calls), 1)
        sent = opener.calls[0]["payload"]
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertEqual(sent["model"], "deepseek-v4-flash")
        self.assertEqual(sent["temperature"], self.config.model.temperature)
        self.assertEqual(sent["top_p"], self.config.model.top_p)
        self.assertEqual(sent["max_tokens"], self.config.model.max_output_tokens)
        self.assertFalse(sent["stream"])
        self.assertNotIn("seed", sent)
        self.assertEqual(result["prompt_tokens"], 15)
        self.assertEqual(result["completion_tokens"], 7)
        self.assertEqual(result["total_tokens"], 22)
        self.assertEqual(result["response_id"], "response-123")
        self.assertEqual(result["request_id"], "request-456")
        self.assertTrue(result["request_id_supported"])
        persisted = "".join(
            path.read_text(encoding="utf-8")
            for path in self.output_root.rglob("*") if path.is_file())
        self.assertNotIn(SECRET, persisted)
        self.assertFalse(result["judge_accessed"])
        self.assertFalse(result["formal_pilot_data_generated"])
        self.assertFalse(list(self.output_root.rglob("results.jsonl")))
        self.assertFalse(list(self.output_root.rglob("summary.json")))

    def test_nonempty_reasoning_content_fails(self):
        result, _ = self.run_check(response_payload(reasoning_content="hidden thought"))
        self.assertFalse(result["passed"])
        self.assertIn("reasoning_content_not_empty", result["failure_reasons"])

    def test_complete_forwards_per_call_dynamic_max_tokens(self):
        opener = CapturingOpener(FakeHttpResponse(response_payload()))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": SECRET}):
            client = DeepSeekCompatibleClient(self.config.model, opener=opener)
            client.complete(
                role="general_guidance",
                problem_id="problem",
                condition="initial",
                system_prompt="system",
                user_prompt="user",
                max_output_tokens=1229,
            )
        self.assertEqual(opener.calls[0]["payload"]["max_tokens"], 1229)
        self.assertEqual(self.config.model.max_output_tokens, 16384)

    def test_missing_completion_tokens_fails_without_estimation(self):
        result, _ = self.run_check(response_payload(completion_tokens=None))
        self.assertFalse(result["passed"])
        self.assertIn("completion_tokens_missing_or_invalid", result["failure_reasons"])
        self.assertIsNone(result["completion_tokens"])

    def test_output_inside_repository_is_rejected_before_network(self):
        opener = CapturingOpener(FakeHttpResponse(response_payload()))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": SECRET}):
            client = DeepSeekCompatibleClient(self.config.model, opener=opener)
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                run_api_compatibility_check(
                    self.config, client, ROOT / "experiments" / "runs",
                    project_root=ROOT)
        self.assertEqual(opener.calls, [])


if __name__ == "__main__":
    unittest.main()
