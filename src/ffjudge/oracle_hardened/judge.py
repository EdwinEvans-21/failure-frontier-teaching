from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid

from ..models import ProblemSpec
from ..runner import DockerJudge, equivalent, run_limited_process

PREFIX = b"FFJUDGE_V3_BATCH_RESULT:"
STATUS_TO_VERDICT = {
    "syntax_error": "CE", "invalid_submission": "INVALID_SUBMISSION",
    "runtime_error": "RE", "invalid_result": "RE",
    "time_limit_exceeded": "TLE", "worker_error": "INTERNAL_ERROR",
}


def canonical_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def worker_request(spec: ProblemSpec, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the only payload mounted into the container; excludes oracle data."""
    return {
        "entrypoint": spec.entrypoint.__dict__,
        "time_seconds": spec.limits.time_seconds,
        "cases": [{"args": deepcopy(c.get("args", [])), "kwargs": deepcopy(c.get("kwargs", {}))} for c in cases],
    }


class OracleHardenedJudge:
    """Batch extension of DockerJudge; expected values never enter the container."""

    def __init__(self, image: str = "ffjudge-python:latest") -> None:
        self.image = image
        self.base = DockerJudge(image=image)

    def judge(self, submission: Path, problem_json: Path, cases: list[dict[str, Any]], *, layer: str) -> dict[str, Any]:
        self.base.ensure_available()
        spec = ProblemSpec.load(problem_json)
        name = f"ffjudge-v3-{uuid.uuid4().hex}"
        harness = Path(__file__).with_name("batch_harness.py")
        with tempfile.TemporaryDirectory(prefix="ffjudge-v3-") as td:
            workspace = Path(td)
            shutil.copy2(submission, workspace / "solution.py")
            request = worker_request(spec, cases)
            (workspace / "batch.json").write_text(json.dumps(request, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            command = self.base._docker_command(workspace, harness, spec, container_name=name)
            output = None
            oom = False
            try:
                output = run_limited_process(command, timeout=spec.limits.time_seconds + 35.0)
                oom = self.base._inspect_oom_killed(name)
            finally:
                self.base._remove_container(name)
        if output.timed_out:
            result = {"verdict": "INTERNAL_ERROR", "reason": "infrastructure_watchdog", "layer": layer}
        elif oom:
            result = {"verdict": "MLE", "reason": "oom_killed", "layer": layer}
        else:
            payload = self._parse(output.stdout)
            if payload is None:
                result = {"verdict": "INTERNAL_ERROR", "reason": "invalid_worker_record", "layer": layer}
            elif payload.get("status") != "ok":
                result = {"verdict": STATUS_TO_VERDICT.get(payload.get("status"), "INTERNAL_ERROR"), "reason": payload.get("error_type", payload.get("status")), "layer": layer}
            else:
                result = self._compare(payload.get("outcomes", []), cases, spec, layer)
        stable = {k: v for k, v in result.items() if k not in {"runtime_ms", "case_runtime_ms"}}
        result["stable_artifact_sha256"] = canonical_sha256(stable)
        result["judge_policy"] = "judge_v3_oracle_hardened"
        return result

    @staticmethod
    def _parse(stdout: bytes) -> dict[str, Any] | None:
        for line in reversed(stdout.splitlines()):
            if line.startswith(PREFIX):
                try:
                    value = json.loads(line[len(PREFIX):])
                    return value if isinstance(value, dict) else None
                except json.JSONDecodeError:
                    return None
        return None

    @staticmethod
    def _compare(outcomes: list[dict[str, Any]], cases: list[dict[str, Any]], spec: ProblemSpec, layer: str) -> dict[str, Any]:
        runtimes: list[int] = []
        for index, outcome in enumerate(outcomes):
            runtimes.append(max(0, int(outcome.get("runtime_ms", 0))))
            status = outcome.get("status")
            if status != "ok":
                return {"verdict": STATUS_TO_VERDICT.get(status, "INTERNAL_ERROR"), "reason": outcome.get("error_type", status), "case_id": cases[index]["case_id"], "case_runtime_ms": runtimes[-1], "runtime_ms": sum(runtimes), "layer": layer}
            if not equivalent(outcome.get("actual"), cases[index]["expected"], spec):
                return {"verdict": "WA", "reason": "counterexample", "case_id": cases[index]["case_id"], "case_index": index, "actual": outcome.get("actual"), "expected": cases[index]["expected"], "input": {"args": cases[index].get("args", []), "kwargs": cases[index].get("kwargs", {})}, "case_runtime_ms": runtimes[-1], "runtime_ms": sum(runtimes), "layer": layer}
        if len(outcomes) != len(cases):
            return {"verdict": "INTERNAL_ERROR", "reason": "incomplete_batch", "completed": len(outcomes), "total": len(cases), "runtime_ms": sum(runtimes), "layer": layer}
        return {"verdict": "AC", "reason": "all_cases_passed", "passed": len(cases), "runtime_ms": sum(runtimes), "layer": layer}
