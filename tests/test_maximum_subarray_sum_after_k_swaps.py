from itertools import product
from pathlib import Path
import importlib.util
import json
import unittest

from ffjudge.models import ProblemSpec
from ffjudge.oracles.maximum_subarray_sum_after_k_swaps import (
    kadane_nonempty,
    max_sum_bfs,
    max_sum_reference,
    max_sum_sorting_oracle,
)
from ffjudge.runner import equivalent


class MaximumSubarraySumAfterKSwapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = (
            Path(__file__).parents[1]
            / "examples"
            / "maximum_subarray_sum_after_k_swaps"
        )
        cls.spec = ProblemSpec.load(cls.fixture_root / "problem.json")
        cls.public_cases = json.loads(
            (cls.fixture_root / "public_tests.json").read_text(encoding="utf-8")
        )
        cls.hidden_cases = json.loads(
            (cls.fixture_root / "hidden_tests.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def load_solution(path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Solution()

    def test_metadata_registers_hard_optimization_problem(self) -> None:
        self.assertEqual(
            self.spec.problem_id,
            "lc-3962-maximum-subarray-sum-after-k-swaps",
        )
        self.assertEqual(self.spec.difficulty, "hard")
        self.assertEqual(self.spec.role, "hard_optimization_candidate")
        self.assertEqual(self.spec.comparison, "exact")
        self.assertEqual(self.spec.entrypoint.class_name, "Solution")
        self.assertEqual(self.spec.entrypoint.method, "maxSum")
        self.assertEqual(self.spec.limits.time_seconds, 20.0)
        self.assertEqual(self.spec.limits.memory_mb, 128)

    def test_exhaustive_small_arrays_match_explicit_bfs(self) -> None:
        checked = 0
        for n in range(1, 7):
            for values in product((-2, 0, 3), repeat=n):
                nums = list(values)
                for k in range(n + 1):
                    expected = max_sum_bfs(nums, k)
                    self.assertEqual(max_sum_reference(nums, k), expected)
                    self.assertEqual(max_sum_sorting_oracle(nums, k), expected)
                    checked += 1
        for n in (7, 8):
            for values in product((-1, 2), repeat=n):
                nums = list(values)
                for k in range(n + 1):
                    self.assertEqual(
                        max_sum_reference(nums, k), max_sum_bfs(nums, k)
                    )
                    checked += 1
        self.assertEqual(checked, 10_435)

    def test_reverse_invariant(self) -> None:
        checked = 0
        for n in range(1, 6):
            for values in product((-3, 0, 4), repeat=n):
                nums = list(values)
                for k in range(n + 1):
                    self.assertEqual(
                        max_sum_reference(nums, k),
                        max_sum_reference(nums[::-1], k),
                    )
                    checked += 1
        self.assertEqual(checked, 2_004)

    def test_monotonic_invariant(self) -> None:
        checked = 0
        for n in range(1, 6):
            for values in product((-3, 0, 4), repeat=n):
                nums = list(values)
                answers = [max_sum_reference(nums, k) for k in range(n + 1)]
                for before, after in zip(answers, answers[1:]):
                    self.assertGreaterEqual(after, before)
                    checked += 1
        self.assertEqual(checked, 1_641)

    def test_zero_swap_invariant(self) -> None:
        checked = 0
        for n in range(1, 8):
            for values in product((-3, 0, 4), repeat=n):
                nums = list(values)
                self.assertEqual(max_sum_reference(nums, 0), kadane_nonempty(nums))
                checked += 1
        self.assertEqual(checked, 3_279)

    def test_positive_scaling_invariant(self) -> None:
        checked = 0
        for n in range(1, 6):
            for values in product((-3, 0, 4), repeat=n):
                nums = list(values)
                for k in range(n + 1):
                    expected = max_sum_reference(nums, k)
                    for scale in (2, 3):
                        self.assertEqual(
                            max_sum_reference(
                                [value * scale for value in nums], k
                            ),
                            expected * scale,
                        )
                        checked += 1
        self.assertEqual(checked, 4_008)

    def test_large_k_invariant(self) -> None:
        checked = 0
        for n in range(1, 8):
            for values in product((-3, 0, 4), repeat=n):
                nums = list(values)
                positive_sum = sum(value for value in nums if value > 0)
                expected = positive_sum if positive_sum else max(nums)
                self.assertEqual(max_sum_reference(nums, n), expected)
                checked += 1
        self.assertEqual(checked, 3_279)

    def test_formal_cases_follow_contract_and_expected_values(self) -> None:
        self.assertEqual(len(self.public_cases), 4)
        self.assertEqual(len(self.hidden_cases), 29)
        for case in self.public_cases + self.hidden_cases:
            self.assertEqual(set(case), {"args", "expected"})
            nums, k = case["args"]
            self.assertGreaterEqual(len(nums), 1)
            self.assertLessEqual(len(nums), 1_500)
            self.assertTrue(all(type(value) is int
                                and -100_000 <= value <= 100_000
                                for value in nums))
            self.assertIs(type(k), int)
            self.assertGreaterEqual(k, 0)
            self.assertLessEqual(k, len(nums))
            self.assertIs(type(case["expected"]), int)

        for case in self.public_cases + self.hidden_cases[:22]:
            nums, k = case["args"]
            self.assertEqual(case["expected"], max_sum_reference(nums, k))

    def test_hidden_suite_covers_required_families_and_stress(self) -> None:
        arguments = [case["args"] for case in self.hidden_cases]
        self.assertTrue(any(len(nums) == 1 for nums, _ in arguments))
        self.assertTrue(any(k == 0 for _, k in arguments))
        self.assertTrue(any(k == len(nums) for nums, k in arguments))
        self.assertTrue(any(all(value > 0 for value in nums)
                            for nums, _ in arguments))
        self.assertTrue(any(all(value < 0 for value in nums)
                            for nums, _ in arguments))
        self.assertTrue(any(set(nums) == {0} for nums, _ in arguments))
        self.assertTrue(any(len(nums) - len(set(nums)) >= 50
                            for nums, _ in arguments))
        self.assertTrue(any(100_000 in nums and -100_000 in nums
                            for nums, _ in arguments))
        self.assertEqual(sum(len(nums) == 1_500 for nums, _ in arguments), 7)
        self.assertEqual(
            {k for nums, k in arguments if len(nums) == 1_500},
            {0, 1, 200, 500, 750, 1_500},
        )

    def test_required_interval_selection_regression(self) -> None:
        nums = [-1, -2, -3, -4, 6, -6, -7, 7, -9, -10, 7]
        self.assertIn(
            {"args": [nums, 1], "expected": 14}, self.hidden_cases
        )
        self.assertEqual(max_sum_reference(nums, 1), 14)

    def test_at_most_k_semantics_include_both_exact_and_fewer_swaps(self) -> None:
        exact_nums = [5, -10, 4, -10, 3, -10, 2]
        self.assertGreater(
            max_sum_reference(exact_nums, 2),
            max_sum_reference(exact_nums, 1),
        )
        fewer_nums = [-5, 2, -5, 2]
        self.assertEqual(
            max_sum_reference(fewer_nums, 2),
            max_sum_reference(fewer_nums, 1),
        )

    def test_reference_submission_passes_every_formal_case(self) -> None:
        solution = self.load_solution(self.fixture_root / "accepted.py")
        for case in self.public_cases + self.hidden_cases:
            actual = solution.maxSum(*case["args"])
            self.assertTrue(equivalent(actual, case["expected"], self.spec))

    def test_wrong_answer_submissions_are_deterministically_caught(self) -> None:
        cases = self.public_cases + self.hidden_cases[:22]
        for filename in (
            "wrong_force_exactly_k.py",
            "wrong_global_largest.py",
        ):
            solution = self.load_solution(self.fixture_root / filename)
            with self.subTest(submission=filename):
                self.assertTrue(any(
                    not equivalent(
                        solution.maxSum(*case["args"]),
                        case["expected"],
                        self.spec,
                    )
                    for case in cases
                ))

    def test_sorting_submission_is_correct_before_formal_stress(self) -> None:
        solution = self.load_solution(
            self.fixture_root / "wrong_sort_every_interval.py"
        )
        for case in self.public_cases + self.hidden_cases[:22]:
            self.assertEqual(solution.maxSum(*case["args"]), case["expected"])
        self.assertTrue(all(
            len(case["args"][0]) == 1_500 for case in self.hidden_cases[22:]
        ))

    def test_statement_omits_removed_special_instruction(self) -> None:
        statement = (self.fixture_root / "README.md").read_text(
            encoding="utf-8"
        )
        removed_name = "luntha" + "rivo"
        self.assertNotIn(removed_name, statement.casefold())


if __name__ == "__main__":
    unittest.main()
