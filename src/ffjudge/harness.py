from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.util
import json
import os
import signal
import time

WORKSPACE = Path(os.environ.get("FFJUDGE_WORKSPACE", "/workspace"))
RESULT_PREFIX = b"FFJUDGE_WORKER_RESULT:"
_OS_WRITE = os.write
_SAFE_ERROR_TYPES = {
    error_type: error_type.__name__
    for error_type in (
        ArithmeticError,
        AssertionError,
        IndexError,
        KeyError,
        MemoryError,
        NameError,
        NotImplementedError,
        OverflowError,
        RecursionError,
        RuntimeError,
        StopIteration,
        TypeError,
        ValueError,
        ZeroDivisionError,
    )
}


def emit(**payload: Any) -> None:
    encoded = json.dumps(payload, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    _OS_WRITE(1, b"\n" + RESULT_PREFIX + encoded + b"\n")


def load_submission() -> Any:
    spec = importlib.util.spec_from_file_location("submission",
                                                  WORKSPACE / "solution.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_callable(module: Any, entrypoint: dict[str, Any]) -> Any:
    if entrypoint["kind"] == "function":
        return getattr(module, entrypoint["function"])
    instance = getattr(module, entrypoint["class_name"])()
    return getattr(instance, entrypoint["method"])


class ExecutionTimedOut(Exception):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise ExecutionTimedOut


def error_category(error: BaseException) -> str:
    return _SAFE_ERROR_TYPES.get(type(error), "UserException")


def main() -> None:
    try:
        request = json.loads(
            (WORKSPACE / "case.json").read_text(encoding="utf-8"))
        entrypoint = request["entrypoint"]
        args = request.get("args", [])
        kwargs = request.get("kwargs", {})
        time_seconds = float(request["time_seconds"])
        if time_seconds <= 0:
            raise ValueError("time_seconds must be positive")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        emit(status="worker_error",
             error_type="InvalidWorkerRequest",
             runtime_ms=0)
        return

    started = time.monotonic()
    previous_handler = None
    if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
        previous_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, time_seconds)

    try:
        try:
            module = load_submission()
            function = resolve_callable(module, entrypoint)
        except SyntaxError:
            emit(
                status="syntax_error",
                error_type="SyntaxError",
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return
        except ExecutionTimedOut:
            emit(
                status="time_limit_exceeded",
                error_type="ExecutionTimedOut",
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return
        except (ImportError, AttributeError, TypeError, ValueError) as error:
            emit(
                status="invalid_submission",
                error_type=error_category(error),
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return
        except BaseException as error:
            emit(
                status="runtime_error",
                error_type=error_category(error),
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return

        try:
            actual = function(*args, **kwargs)
        except ExecutionTimedOut:
            emit(
                status="time_limit_exceeded",
                error_type="ExecutionTimedOut",
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return
        except BaseException as error:
            emit(
                status="runtime_error",
                error_type=error_category(error),
                runtime_ms=int((time.monotonic() - started) * 1000),
            )
            return

        runtime_ms = int((time.monotonic() - started) * 1000)
        try:
            emit(status="ok", actual=actual, runtime_ms=runtime_ms)
        except (TypeError, ValueError, OverflowError):
            emit(status="invalid_result",
                 error_type="NonJsonResult",
                 runtime_ms=runtime_ms)
    finally:
        if previous_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
