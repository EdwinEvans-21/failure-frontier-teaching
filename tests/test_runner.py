from pathlib import Path
from unittest import mock
import json
import sys
import tempfile
import unittest

from ffjudge.models import Entrypoint, Limits, ProblemSpec, Verdict
from ffjudge.runner import (
    DockerJudge,
    OUTPUT_LIMIT_BYTES,
    ProcessOutput,
    WorkerResult,
    equivalent,
    run_limited_process,
)


class FakeDockerJudge(DockerJudge):

    def __init__(
            self, results: list[tuple[WorkerResult | None, bool,
                                      bool]]) -> None:
        super().__init__()
        self.results = iter(results)

    def ensure_available(self) -> None:
        pass

    def _run_case(self, submission, spec, case):
        return next(self.results)


class DockerJudgeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.spec = ProblemSpec(
            problem_id="x",
            title="X",
            entrypoint=Entrypoint(kind="class_method",
                                  class_name="Solution",
                                  method="solve"),
            limits=Limits(time_seconds=1, memory_mb=128, cpus=0.5, pids=32),
        )

    def make_inputs(
        self, tests: list[dict]
    ) -> tuple[tempfile.TemporaryDirectory, Path, Path, Path]:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        submission = root / "solution.py"
        problem = root / "problem.json"
        tests_path = root / "tests.json"
        submission.write_text("class Solution: pass\n", encoding="utf-8")
        problem.write_text(json.dumps(self.spec.to_dict()), encoding="utf-8")
        tests_path.write_text(json.dumps(tests), encoding="utf-8")
        return directory, submission, problem, tests_path

    def make_custom_inputs(
        self, tests: list[dict]
    ) -> tuple[tempfile.TemporaryDirectory, Path, Path, Path]:
        custom_spec = ProblemSpec(
            problem_id="construction",
            title="Construction",
            entrypoint=Entrypoint(
                kind="class_method",
                class_name="Solution",
                method="constructGrid",
            ),
            comparison="custom",
            checker="exact_monotone_paths",
            limits=self.spec.limits,
        )
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        submission = root / "solution.py"
        problem = root / "problem.json"
        tests_path = root / "tests.json"
        submission.write_text("class Solution: pass\n", encoding="utf-8")
        problem.write_text(json.dumps(custom_spec.to_dict()), encoding="utf-8")
        tests_path.write_text(json.dumps(tests), encoding="utf-8")
        return directory, submission, problem, tests_path

    def test_workspace_contains_only_current_input_and_no_expected(
            self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            submission = workspace / "source.py"
            submission.write_text("pass\n", encoding="utf-8")
            case = {"args": [[1, 2], 3], "kwargs": {}, "expected": [0, 1]}
            output = workspace / "worker"
            output.mkdir()
            DockerJudge._prepare_workspace(output, submission, self.spec, case)
            payload = json.loads(
                (output / "case.json").read_text(encoding="utf-8"))
            self.assertNotIn("expected", payload)
            self.assertEqual(payload["args"], case["args"])
            self.assertEqual(sorted(path.name for path in output.iterdir()),
                             ["case.json", "solution.py"])

    def test_workspace_does_not_include_custom_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            submission = workspace / "source.py"
            submission.write_text("pass\n", encoding="utf-8")
            case = {
                "args": [2, 2, 2],
                "oracle": {"feasible": True},
            }
            output = workspace / "worker"
            output.mkdir()
            DockerJudge._prepare_workspace(output, submission, self.spec, case)
            payload = json.loads(
                (output / "case.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("oracle", payload)
            self.assertNotIn("feasible", json.dumps(payload))
            self.assertEqual(payload["args"], [2, 2, 2])

    def test_docker_command_does_not_mount_tests_and_keeps_container_for_inspect(
            self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = DockerJudge()._docker_command(root,
                                                    root / "harness.py",
                                                    self.spec,
                                                    container_name="case")
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertNotIn("--rm", command)
        self.assertNotIn("tests.json", joined)
        self.assertNotIn("expected", joined)

    def test_host_generates_accepted_and_wrong_answer_from_actual(
            self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [1],
            "expected":
            2
        }])
        with directory:
            accepted = FakeDockerJudge([(WorkerResult("ok", 4, actual=2),
                                         False, False)])
            wrong = FakeDockerJudge([(WorkerResult("ok", 4,
                                                   actual=3), False, False)])
            self.assertIs(
                accepted.judge(submission, problem, tests_path).verdict,
                Verdict.ACCEPTED)
            self.assertIs(
                wrong.judge(submission, problem, tests_path).verdict,
                Verdict.WRONG_ANSWER)

    def test_missing_worker_result_is_runtime_error_not_accepted(self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(None, False, False)])
            self.assertIs(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.RUNTIME_ERROR)

    def test_exit_137_without_oom_evidence_is_not_mle(self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(None, False, False)])
            self.assertIsNot(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.MEMORY_LIMIT_EXCEEDED,
            )

    def test_oom_inspect_evidence_is_required_for_mle(self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(None, True, False)])
            self.assertIs(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.MEMORY_LIMIT_EXCEEDED,
            )

    def test_syntax_status_maps_to_syntax_error(self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(WorkerResult("syntax_error",
                                                   2,
                                                   error_type="SyntaxError"),
                                      False, False)])
            self.assertIs(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.SYNTAX_ERROR)

    def test_runtime_status_preserves_runtime_error_behavior(self) -> None:
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(WorkerResult("runtime_error",
                                                   2,
                                                   error_type="RuntimeError"),
                                      False, False)])
            self.assertIs(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.RUNTIME_ERROR)

    def test_fake_accepted_payload_is_not_trusted(self) -> None:
        payload = b'{"verdict":"ACCEPTED","phase":"hidden"}\n'
        self.assertIsNone(DockerJudge._parse_worker_output(payload))
        prefixed = b'FFJUDGE_WORKER_RESULT:{"status":"ACCEPTED","runtime_ms":0}\n'
        worker = DockerJudge._parse_worker_output(prefixed)
        self.assertEqual(worker.status, "ACCEPTED")
        directory, submission, problem, tests_path = self.make_inputs([{
            "args": [],
            "expected":
            None
        }])
        with directory:
            judge = FakeDockerJudge([(worker, False, False)])
            self.assertIs(
                judge.judge(submission, problem, tests_path).verdict,
                Verdict.INTERNAL_ERROR,
            )

    def test_untrusted_error_type_is_sanitized(self) -> None:
        payload = (
            b'FFJUDGE_WORKER_RESULT:{"status":"runtime_error","runtime_ms":1,'
            b'"error_type":"secret supplied by submission"}\n')
        worker = DockerJudge._parse_worker_output(payload)
        self.assertEqual(worker.error_type, "UserException")

    def test_output_is_bounded_for_stdout_and_stderr(self) -> None:
        size = OUTPUT_LIMIT_BYTES * 3
        command = [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.write('o'*{size}); sys.stderr.write('e'*{size})",
        ]
        output = run_limited_process(command, timeout=5)
        self.assertLessEqual(len(output.stdout), OUTPUT_LIMIT_BYTES)
        self.assertLessEqual(len(output.stderr), OUTPUT_LIMIT_BYTES)
        self.assertTrue(output.stdout_truncated)
        self.assertTrue(output.stderr_truncated)

    def test_finally_removes_container_when_inspect_fails(self) -> None:
        judge = DockerJudge()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            submission = root / "solution.py"
            submission.write_text("pass\n", encoding="utf-8")
            with mock.patch("ffjudge.runner.run_limited_process",
                            return_value=ProcessOutput(
                                0, b"", b"")), mock.patch.object(
                                    judge,
                                    "_inspect_oom_killed",
                                    side_effect=RuntimeError(
                                        "inspect failed")), mock.patch.object(
                                            judge,
                                            "_remove_container") as remove:
                with self.assertRaises(RuntimeError):
                    judge._run_case(submission, self.spec, {
                        "args": [],
                        "expected": None
                    })
                remove.assert_called_once()

    def test_custom_checker_generates_final_verdict_on_host(self) -> None:
        case = {"args": [2, 2, 2], "oracle": {"feasible": True}}
        directory, submission, problem, tests_path = self.make_custom_inputs([case])
        with directory:
            accepted = FakeDockerJudge([
                (WorkerResult("ok", 3, actual=["..", ".."]), False, False)
            ])
            wrong = FakeDockerJudge([
                (WorkerResult("ok", 3, actual=[]), False, False)
            ])
            accepted_result = accepted.judge(
                submission, problem, tests_path, phase="hidden"
            )
            wrong_result = wrong.judge(
                submission, problem, tests_path, phase="hidden"
            )
            self.assertIs(accepted_result.verdict, Verdict.ACCEPTED)
            self.assertIs(wrong_result.verdict, Verdict.WRONG_ANSWER)
            self.assertEqual(
                wrong_result.checker_failure_category,
                "unexpected_empty",
            )
            feedback = wrong_result.model_feedback()
            self.assertEqual(
                feedback,
                {
                    "verdict": "WRONG_ANSWER",
                    "phase": "hidden",
                    "message": "A hidden case failed.",
                },
            )


class ComparisonTests(unittest.TestCase):

    def test_exact_requires_same_type_and_value(self) -> None:
        spec = ProblemSpec(
            problem_id="x",
            title="X",
            entrypoint=Entrypoint(kind="function", function="solve"),
        )
        self.assertTrue(equivalent([1, 2], [1, 2], spec))
        self.assertFalse(equivalent(True, 1, spec))
        self.assertFalse(equivalent(1, True, spec))
        self.assertFalse(equivalent([True], [1], spec))

    def test_unordered_outer_sequence(self) -> None:
        spec = ProblemSpec(
            problem_id="x",
            title="X",
            entrypoint=Entrypoint(kind="function", function="solve"),
            comparison="unordered",
        )
        self.assertTrue(equivalent([2, 1], [1, 2], spec))


if __name__ == "__main__":
    unittest.main()
