from pathlib import Path
import json
import tempfile
import unittest

from ffjudge.models import ProblemSpec, Verdict, JudgeResult


class ProblemSpecTests(unittest.TestCase):

    def test_load_problem_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem.json"
            path.write_text(
                json.dumps({
                    "problem_id": "sum",
                    "title": "Sum",
                    "entrypoint": {
                        "kind": "function",
                        "function": "solve"
                    },
                }),
                encoding="utf-8",
            )
            spec = ProblemSpec.load(path)
        self.assertEqual(spec.entrypoint.function, "solve")
        self.assertEqual(spec.limits.memory_mb, 256)

    def test_rejects_invalid_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem.json"
            path.write_text(
                json.dumps({
                    "problem_id": "bad",
                    "title": "Bad",
                    "entrypoint": {
                        "kind": "class_method",
                        "class_name": "Solution",
                    },
                }),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                ProblemSpec.load(path)

    def test_custom_comparison_requires_checker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem.json"
            path.write_text(
                json.dumps({
                    "problem_id": "construction",
                    "title": "Construction",
                    "entrypoint": {"kind": "function", "function": "solve"},
                    "comparison": "custom",
                }),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                ProblemSpec.load(path)

    def test_result_round_trip(self) -> None:
        result = JudgeResult(
            verdict=Verdict.WRONG_ANSWER,
            phase="hidden",
            passed=2,
            total=5,
            runtime_ms=13,
            message="A hidden case failed.",
        )
        self.assertEqual(JudgeResult.from_dict(result.to_dict()), result)

    def test_hidden_model_feedback_does_not_leak_case_progress(self) -> None:
        result = JudgeResult(
            verdict=Verdict.WRONG_ANSWER,
            phase="hidden",
            passed=4,
            total=5,
            runtime_ms=13,
            message="A hidden case failed.",
            case_index=None,
        )
        feedback = result.model_feedback()
        self.assertNotIn("passed", feedback)
        self.assertNotIn("total", feedback)
        self.assertNotIn("case_index", feedback)
        self.assertNotIn("runtime_ms", feedback)

    def test_hidden_model_feedback_contains_only_controlled_fields(
            self) -> None:
        result = JudgeResult(
            verdict=Verdict.RUNTIME_ERROR,
            phase="hidden",
            passed=3,
            total=8,
            runtime_ms=99,
            message="Submission failed during execution.",
            case_index=None,
        )
        feedback = result.model_feedback()
        self.assertEqual(
            set(feedback),
            {"verdict", "phase", "message"},
        )
        serialized = json.dumps(feedback)
        for secret in ("args", "expected", "actual", "stdout", "stderr"):
            self.assertNotIn(secret, serialized)

    def test_hidden_model_feedback_omits_checker_category(self) -> None:
        result = JudgeResult(
            verdict=Verdict.WRONG_ANSWER,
            phase="hidden",
            passed=0,
            total=1,
            runtime_ms=4,
            message="A hidden case failed.",
            checker_failure_category="path_count_mismatch",
        )
        feedback = result.model_feedback()
        self.assertNotIn("checker_failure_category", feedback)
        serialized = json.dumps(feedback)
        self.assertNotIn("path_count", serialized)
        self.assertNotIn("feasible", serialized)


if __name__ == "__main__":
    unittest.main()
