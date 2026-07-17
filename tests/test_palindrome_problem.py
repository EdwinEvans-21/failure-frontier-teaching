from pathlib import Path
import importlib.util
import json
import unittest

from ffjudge.models import ProblemSpec
from ffjudge.runner import equivalent


class PalindromeProblemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = (
            Path(__file__).parents[1] / "examples" / "palindrome_number"
        )
        cls.spec = ProblemSpec.load(cls.fixture_root / "problem.json")
        cls.public_cases = json.loads(
            (cls.fixture_root / "public_tests.json").read_text(encoding="utf-8")
        )
        cls.hidden_cases = json.loads(
            (cls.fixture_root / "hidden_tests.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def reference(x: int) -> bool:
        if x < 0:
            return False
        original = x
        reversed_number = 0
        while x:
            reversed_number = reversed_number * 10 + x % 10
            x //= 10
        return reversed_number == original

    @staticmethod
    def load_solution(path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Solution()

    def test_metadata_marks_easy_sanity_control_problem(self) -> None:
        self.assertEqual(self.spec.problem_id, "lc-0009-palindrome-number")
        self.assertEqual(self.spec.difficulty, "easy")
        self.assertEqual(self.spec.role, "sanity_control")
        self.assertEqual(self.spec.entrypoint.class_name, "Solution")
        self.assertEqual(self.spec.entrypoint.method, "isPalindrome")
        self.assertEqual(self.spec.comparison, "exact")
        self.assertEqual(
            self.spec.source_url,
            "https://leetcode.com/problems/palindrome-number/",
        )

    def test_resource_limits_are_deliberate(self) -> None:
        self.assertEqual(self.spec.limits.time_seconds, 0.5)
        self.assertEqual(self.spec.limits.memory_mb, 64)
        self.assertEqual(self.spec.limits.pids, 32)

    def test_public_cases_are_small_and_typical(self) -> None:
        self.assertLessEqual(len(self.public_cases), 3)
        self.assertTrue(all(type(case["expected"]) is bool for case in self.public_cases))

    def test_all_cases_follow_contract_and_reference_oracle(self) -> None:
        for case in self.public_cases + self.hidden_cases:
            self.assertEqual(len(case.get("args", [])), 1)
            value = case["args"][0]
            self.assertIs(type(value), int)
            self.assertGreaterEqual(value, -(2**31))
            self.assertLessEqual(value, 2**31 - 1)
            self.assertIs(type(case["expected"]), bool)
            self.assertIs(case["expected"], self.reference(value))

    def test_hidden_cases_cover_required_categories(self) -> None:
        values = [case["args"][0] for case in self.hidden_cases]
        positives = [value for value in values if value >= 0]
        negatives = [value for value in values if value < 0]

        self.assertTrue(any(value == 0 for value in values))
        self.assertTrue(any(0 < value < 10 for value in values))
        self.assertTrue(
            any(
                value > 9
                and len(str(value)) % 2 == 1
                and self.reference(value)
                for value in positives
            )
        )
        self.assertTrue(
            any(
                len(str(value)) % 2 == 0 and self.reference(value)
                for value in positives
            )
        )
        self.assertTrue(
            any(value > 0 and not self.reference(value) for value in positives)
        )
        self.assertGreaterEqual(len(negatives), 3)
        self.assertTrue(all(not self.reference(value) for value in negatives))
        self.assertTrue(any(value > 0 and value % 10 == 0 for value in positives))

        middle_zero_cases = [
            value
            for value in positives
            if len(str(value)) > 2 and "0" in str(value)[1:-1]
        ]
        self.assertTrue(any(self.reference(value) for value in middle_zero_cases))
        self.assertTrue(any(not self.reference(value) for value in middle_zero_cases))
        self.assertTrue(any(abs(value) >= 2_147_000_000 for value in values))

    def test_public_and_hidden_inputs_do_not_overlap(self) -> None:
        public_inputs = {tuple(case["args"]) for case in self.public_cases}
        hidden_inputs = {tuple(case["args"]) for case in self.hidden_cases}
        self.assertTrue(public_inputs.isdisjoint(hidden_inputs))

    def test_exact_rejects_integer_one_for_true(self) -> None:
        self.assertFalse(equivalent(1, True, self.spec))
        self.assertTrue(equivalent(True, True, self.spec))

    def test_reference_solution_passes_every_case(self) -> None:
        solution = self.load_solution(self.fixture_root / "accepted.py")
        for case in self.public_cases + self.hidden_cases:
            actual = solution.isPalindrome(*case["args"])
            self.assertIs(type(actual), bool)
            self.assertIs(actual, case["expected"])

    def test_representative_wrong_solutions_are_caught(self) -> None:
        wrong_submissions = [
            "wrong.py",
            "wrong_returns_int.py",
            "wrong_abs_value.py",
            "wrong_first_last_only.py",
            "wrong_zero_is_false.py",
        ]
        cases = self.public_cases + self.hidden_cases
        for filename in wrong_submissions:
            with self.subTest(submission=filename):
                solution = self.load_solution(self.fixture_root / filename)
                caught = any(
                    not equivalent(
                        solution.isPalindrome(*case["args"]),
                        case["expected"],
                        self.spec,
                    )
                    for case in cases
                )
                self.assertTrue(caught)


if __name__ == "__main__":
    unittest.main()
