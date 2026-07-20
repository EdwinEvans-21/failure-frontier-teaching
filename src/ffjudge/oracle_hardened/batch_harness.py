from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.util
import json
import os
import signal
import time

WORKSPACE = Path(os.environ.get("FFJUDGE_WORKSPACE", "/workspace"))
PREFIX = b"FFJUDGE_V3_BATCH_RESULT:"


class ExecutionTimedOut(Exception):
    pass


def _alarm(_signum: int, _frame: Any) -> None:
    raise ExecutionTimedOut


def emit(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    os.write(1, b"\n" + PREFIX + data + b"\n")


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("submission_v3", WORKSPACE / "solution.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve(module: Any, entrypoint: dict[str, Any]) -> Any:
    if entrypoint["kind"] == "function":
        return getattr(module, entrypoint["function"])
    return getattr(getattr(module, entrypoint["class_name"])(), entrypoint["method"])


def category(error: BaseException) -> str:
    allowed = {"ArithmeticError", "AssertionError", "AttributeError", "ImportError", "IndexError", "KeyError", "MemoryError", "NameError", "NotImplementedError", "OverflowError", "RecursionError", "RuntimeError", "StopIteration", "SyntaxError", "TypeError", "ValueError", "ZeroDivisionError"}
    name = type(error).__name__
    return name if name in allowed else "UserException"


def main() -> None:
    try:
        request = json.loads((WORKSPACE / "batch.json").read_text(encoding="utf-8"))
        cases, entrypoint = request["cases"], request["entrypoint"]
        limit = float(request["time_seconds"])
        if not isinstance(cases, list) or limit <= 0:
            raise ValueError
    except Exception:
        emit({"status": "worker_error", "error_type": "InvalidWorkerRequest", "outcomes": []})
        return
    try:
        module = load_module()
    except SyntaxError:
        emit({"status": "syntax_error", "error_type": "SyntaxError", "outcomes": []})
        return
    except BaseException as error:
        emit({"status": "invalid_submission", "error_type": category(error), "outcomes": []})
        return
    prior = signal.signal(signal.SIGALRM, _alarm)
    outcomes: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases):
            started = time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, limit)
            try:
                function = resolve(module, entrypoint)
                actual = function(*case.get("args", []), **case.get("kwargs", {}))
                outcome = {"index": index, "status": "ok", "actual": actual, "runtime_ms": int((time.monotonic()-started)*1000)}
                json.dumps(actual)
            except ExecutionTimedOut:
                outcome = {"index": index, "status": "time_limit_exceeded", "error_type": "ExecutionTimedOut", "runtime_ms": int((time.monotonic()-started)*1000)}
            except (AttributeError, ImportError) as error:
                outcome = {"index": index, "status": "invalid_submission", "error_type": category(error), "runtime_ms": int((time.monotonic()-started)*1000)}
            except (TypeError, ValueError, OverflowError) as error:
                outcome = {"index": index, "status": "runtime_error", "error_type": category(error), "runtime_ms": int((time.monotonic()-started)*1000)}
            except BaseException as error:
                outcome = {"index": index, "status": "runtime_error", "error_type": category(error), "runtime_ms": int((time.monotonic()-started)*1000)}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            outcomes.append(outcome)
            if outcome["status"] != "ok":
                break
    finally:
        signal.signal(signal.SIGALRM, prior)
    try:
        emit({"status": "ok", "outcomes": outcomes})
    except (TypeError, ValueError, OverflowError):
        emit({"status": "invalid_result", "error_type": "NonJsonResult", "outcomes": []})


if __name__ == "__main__":
    main()
