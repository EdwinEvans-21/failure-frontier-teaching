from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
import json
import math
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from .models import JudgeResult, ProblemSpec, Verdict

OUTPUT_LIMIT_BYTES = 64 * 1024
DOCKER_STARTUP_GRACE_SECONDS = 2.0
WORKER_RESULT_PREFIX = b"FFJUDGE_WORKER_RESULT:"
SAFE_ERROR_TYPES = {
    "ArithmeticError",
    "AssertionError",
    "AttributeError",
    "ExecutionTimedOut",
    "ImportError",
    "IndexError",
    "InvalidWorkerRequest",
    "KeyError",
    "MemoryError",
    "NameError",
    "NonJsonResult",
    "NotImplementedError",
    "OverflowError",
    "RecursionError",
    "RuntimeError",
    "StopIteration",
    "SyntaxError",
    "TypeError",
    "UserException",
    "ValueError",
    "ZeroDivisionError",
}


class DockerUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessOutput:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


@dataclass(frozen=True)
class WorkerResult:
    status: str
    runtime_ms: int
    actual: Any = None
    error_type: str = ""


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(
            _strict_equal(left, right)
            for left, right in zip(actual, expected))
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            _strict_equal(actual[key], expected[key]) for key in actual)
    return actual == expected


def equivalent(actual: Any, expected: Any, spec: ProblemSpec) -> bool:
    if spec.comparison == "exact":
        return _strict_equal(actual, expected)
    if spec.comparison == "unordered":
        if type(actual) is not type(expected):
            return False
        try:
            return sorted(actual) == sorted(expected)
        except (TypeError, ValueError):
            return False
    if spec.comparison == "float":
        try:
            return math.isclose(
                float(actual),
                float(expected),
                rel_tol=spec.float_tolerance,
                abs_tol=spec.float_tolerance,
            )
        except (TypeError, ValueError, OverflowError):
            return False
    raise ValueError(f"Unsupported comparison mode: {spec.comparison}")


def _read_bounded_tail(stream: BinaryIO, limit: int) -> tuple[bytes, bool]:
    chunks: deque[bytes] = deque()
    retained = 0
    total = 0
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        total += len(chunk)
        chunks.append(chunk)
        retained += len(chunk)
        while retained > limit and chunks:
            excess = retained - limit
            first = chunks[0]
            if len(first) <= excess:
                retained -= len(chunks.popleft())
            else:
                chunks[0] = first[excess:]
                retained -= excess
    return b"".join(chunks), total > limit


def run_limited_process(command: list[str], timeout: float) -> ProcessOutput:
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    assert process.stdout is not None
    assert process.stderr is not None
    captured: dict[str, tuple[bytes, bool]] = {}

    def reader(name: str, stream: BinaryIO) -> None:
        captured[name] = _read_bounded_tail(stream, OUTPUT_LIMIT_BYTES)

    threads = [
        threading.Thread(target=reader,
                         args=("stdout", process.stdout),
                         daemon=True),
        threading.Thread(target=reader,
                         args=("stderr", process.stderr),
                         daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(timeout=5)
    finally:
        for thread in threads:
            thread.join(timeout=5)
        process.stdout.close()
        process.stderr.close()

    stdout, stdout_truncated = captured.get("stdout", (b"", False))
    stderr, stderr_truncated = captured.get("stderr", (b"", False))
    return ProcessOutput(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )


class DockerJudge:
    """Run one untrusted Python test case per constrained Docker container."""

    def __init__(
        self,
        image: str = "ffjudge-python:latest",
        *,
        startup_grace_seconds: float = DOCKER_STARTUP_GRACE_SECONDS,
    ) -> None:
        self.image = image
        self.startup_grace_seconds = startup_grace_seconds

    def ensure_available(self) -> None:
        if shutil.which("docker") is None:
            raise DockerUnavailableError(
                "Docker CLI was not found. Install Docker Desktop or Docker Engine first."
            )

    def build_image(self, project_root: str | Path) -> None:
        self.ensure_available()
        subprocess.run(
            [
                "docker", "build", "-t", self.image,
                str(Path(project_root).resolve())
            ],
            check=True,
        )

    def judge(
        self,
        submission_path: str | Path,
        problem_path: str | Path,
        tests_path: str | Path,
        *,
        phase: str = "hidden",
    ) -> JudgeResult:
        self.ensure_available()
        if phase not in {"public", "hidden"}:
            raise ValueError("phase must be 'public' or 'hidden'")

        submission = Path(submission_path)
        problem_file = Path(problem_path)
        tests_file = Path(tests_path)
        for path in (submission, problem_file, tests_file):
            if not path.is_file():
                raise FileNotFoundError(path)

        spec = ProblemSpec.load(problem_file)
        tests = json.loads(tests_file.read_text(encoding="utf-8"))
        if not isinstance(tests, list):
            raise ValueError("tests file must contain a JSON array")

        total = len(tests)
        runtime_ms = 0
        for index, case in enumerate(tests):
            if not isinstance(case, dict) or "expected" not in case:
                raise ValueError(f"test case {index} must contain expected")
            worker, oom_killed, outer_timeout = self._run_case(
                submission, spec, case)
            if outer_timeout:
                return self._result(
                    Verdict.TIME_LIMIT_EXCEEDED,
                    phase,
                    index,
                    total,
                    runtime_ms + int(spec.limits.time_seconds * 1000),
                    "Execution exceeded the time limit.",
                )
            if oom_killed:
                return self._result(
                    Verdict.MEMORY_LIMIT_EXCEEDED,
                    phase,
                    index,
                    total,
                    runtime_ms,
                    "Execution exceeded the memory limit.",
                )
            if worker is None:
                return self._result(
                    Verdict.RUNTIME_ERROR,
                    phase,
                    index,
                    total,
                    runtime_ms,
                    "Worker exited without a valid result.",
                )

            runtime_ms += worker.runtime_ms
            status_verdict = {
                "syntax_error": Verdict.SYNTAX_ERROR,
                "time_limit_exceeded": Verdict.TIME_LIMIT_EXCEEDED,
                "invalid_submission": Verdict.INVALID_SUBMISSION,
                "invalid_result": Verdict.RUNTIME_ERROR,
                "runtime_error": Verdict.RUNTIME_ERROR,
                "worker_error": Verdict.INTERNAL_ERROR,
            }.get(worker.status)
            if status_verdict is not None:
                return self._result(
                    status_verdict,
                    phase,
                    index,
                    total,
                    runtime_ms,
                    self._status_message(status_verdict, worker.error_type,
                                         phase),
                )
            if worker.status != "ok":
                return self._result(
                    Verdict.INTERNAL_ERROR,
                    phase,
                    index,
                    total,
                    runtime_ms,
                    "Worker returned an unsupported status.",
                )
            if not equivalent(worker.actual, case["expected"], spec):
                return self._result(
                    Verdict.WRONG_ANSWER,
                    phase,
                    index,
                    total,
                    runtime_ms,
                    f"Case {index} failed."
                    if phase == "public" else "A hidden case failed.",
                )

        return JudgeResult(
            verdict=Verdict.ACCEPTED,
            phase=phase,
            passed=total,
            total=total,
            runtime_ms=runtime_ms,
            message="All tests passed.",
            case_index=None,
        )

    def _run_case(
            self, submission: Path, spec: ProblemSpec,
            case: dict[str, Any]) -> tuple[WorkerResult | None, bool, bool]:
        harness = Path(__file__).with_name("harness.py")
        container_name = f"ffjudge-{uuid.uuid4().hex}"
        with tempfile.TemporaryDirectory(prefix="ffjudge-") as temp_dir:
            workspace = Path(temp_dir)
            self._prepare_workspace(workspace, submission, spec, case)
            command = self._docker_command(workspace,
                                           harness,
                                           spec,
                                           container_name=container_name)
            output: ProcessOutput | None = None
            oom_killed = False
            try:
                output = run_limited_process(
                    command,
                    timeout=spec.limits.time_seconds +
                    self.startup_grace_seconds,
                )
                oom_killed = self._inspect_oom_killed(container_name)
            finally:
                self._remove_container(container_name)

        if output is None:
            return None, oom_killed, False
        return self._parse_worker_output(
            output.stdout), oom_killed, output.timed_out

    @staticmethod
    def _prepare_workspace(
        workspace: Path,
        submission: Path,
        spec: ProblemSpec,
        case: dict[str, Any],
    ) -> None:
        shutil.copy2(submission, workspace / "solution.py")
        request = {
            "entrypoint": spec.entrypoint.__dict__,
            "args": case.get("args", []),
            "kwargs": case.get("kwargs", {}),
            "time_seconds": spec.limits.time_seconds,
        }
        (workspace / "case.json").write_text(
            json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def _docker_command(
        self,
        workspace: Path,
        harness: Path,
        spec: ProblemSpec,
        *,
        container_name: str = "ffjudge-test-container",
    ) -> list[str]:
        return [
            "docker",
            "run",
            "--name",
            container_name,
            "--network",
            "none",
            "--memory",
            f"{spec.limits.memory_mb}m",
            "--memory-swap",
            f"{spec.limits.memory_mb}m",
            "--cpus",
            str(spec.limits.cpus),
            "--pids-limit",
            str(spec.limits.pids),
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "-v",
            f"{workspace.resolve()}:/workspace:ro",
            "-v",
            f"{harness.resolve()}:/judge/harness.py:ro",
            self.image,
        ]

    @staticmethod
    def _parse_worker_output(stdout: bytes) -> WorkerResult | None:
        for line in reversed(stdout.splitlines()):
            if not line.startswith(WORKER_RESULT_PREFIX):
                continue
            try:
                payload = json.loads(line[len(WORKER_RESULT_PREFIX):])
                status = payload["status"]
                runtime_ms = payload["runtime_ms"]
                if not isinstance(status, str) or not isinstance(
                        runtime_ms, int):
                    continue
                if status == "ok" and "actual" not in payload:
                    continue
                error_type = payload.get("error_type", "")
                if error_type not in SAFE_ERROR_TYPES:
                    error_type = "UserException"
                return WorkerResult(
                    status=status,
                    runtime_ms=max(0, runtime_ms),
                    actual=payload.get("actual"),
                    error_type=error_type,
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _inspect_oom_killed(container_name: str) -> bool:
        completed = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .State.OOMKilled}}",
                container_name,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip().lower(
        ) == "true"

    @staticmethod
    def _remove_container(container_name: str) -> None:
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    @staticmethod
    def _result(
        verdict: Verdict,
        phase: str,
        passed: int,
        total: int,
        runtime_ms: int,
        message: str,
    ) -> JudgeResult:
        return JudgeResult(
            verdict=verdict,
            phase=phase,
            passed=passed,
            total=total,
            runtime_ms=runtime_ms,
            message=message,
            case_index=passed if phase == "public" else None,
        )

    @staticmethod
    def _status_message(verdict: Verdict, error_type: str, phase: str) -> str:
        messages = {
            Verdict.SYNTAX_ERROR: "Submission contains invalid Python syntax.",
            Verdict.TIME_LIMIT_EXCEEDED: "Execution exceeded the time limit.",
            Verdict.INVALID_SUBMISSION: "Submission entrypoint is invalid.",
            Verdict.RUNTIME_ERROR: "Submission failed during execution.",
            Verdict.INTERNAL_ERROR:
            "The worker could not execute the test case.",
        }
        message = messages[verdict]
        if phase == "public" and error_type:
            message += f" Error type: {error_type[:80]}."
        return message
