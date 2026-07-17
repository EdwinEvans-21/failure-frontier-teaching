from pathlib import Path
import json
import unittest

from ffjudge.checkers.exact_monotone_paths import check_exact_monotone_paths
from ffjudge.models import ProblemSpec
from ffjudge.oracles.exact_monotone_paths import (
    binomial_capacity,
    construct_reference_grid,
    is_feasible,
)


class ExactMonotonePathsOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = (
            Path(__file__).parents[1] / "examples" / "exact_monotone_paths"
        )
        cls.spec = ProblemSpec.load(cls.fixture_root / "problem.json")

    def test_candidate_metadata_and_custom_checker(self) -> None:
        self.assertEqual(self.spec.problem_id, "lc-3988-exact-monotone-paths")
        self.assertEqual(self.spec.role, "medium_upper_construction_candidate")
        self.assertEqual(self.spec.comparison, "custom")
        self.assertEqual(self.spec.checker, "exact_monotone_paths")
        self.assertEqual(self.spec.entrypoint.class_name, "Solution")
        self.assertEqual(self.spec.entrypoint.method, "constructGrid")

    def test_maximum_path_capacity_is_small(self) -> None:
        self.assertEqual(binomial_capacity(10, 10), 48_620)

    def test_explicit_oracle_matches_binomial_capacity_for_all_400_inputs(self) -> None:
        checked = 0
        for m in range(1, 11):
            for n in range(1, 11):
                for k in range(1, 5):
                    with self.subTest(m=m, n=n, k=k):
                        self.assertEqual(
                            is_feasible(m, n, k),
                            binomial_capacity(m, n) >= k,
                        )
                    checked += 1
        self.assertEqual(checked, 400)

    def test_reference_constructor_is_checked_for_all_400_inputs(self) -> None:
        checked = 0
        for m in range(1, 11):
            for n in range(1, 11):
                for k in range(1, 5):
                    feasible = is_feasible(m, n, k)
                    actual = construct_reference_grid(m, n, k)
                    result = check_exact_monotone_paths(
                        actual,
                        [m, n, k],
                        {},
                        {"feasible": feasible},
                    )
                    with self.subTest(m=m, n=n, k=k):
                        self.assertTrue(result.passed, result.failure_category)
                        self.assertEqual(actual == [], not feasible)
                    checked += 1
        self.assertEqual(checked, 400)

    def test_formal_tests_have_no_zero_k_and_use_trusted_labels(self) -> None:
        for filename in ("public_tests.json", "hidden_tests.json"):
            cases = json.loads(
                (self.fixture_root / filename).read_text(encoding="utf-8")
            )
            for case in cases:
                self.assertNotIn("expected", case)
                self.assertIn(case["args"][2], {1, 2, 3, 4})
                self.assertIs(type(case["oracle"]["feasible"]), bool)
                self.assertEqual(
                    case["oracle"]["feasible"],
                    is_feasible(*case["args"]),
                )

    def test_hidden_suite_is_representative_not_exhaustive(self) -> None:
        cases = json.loads(
            (self.fixture_root / "hidden_tests.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(cases), 20)
        self.assertLessEqual(len(cases), 30)
        args = {tuple(case["args"]) for case in cases}
        self.assertTrue(any(m == 1 or n == 1 for m, n, _ in args))
        self.assertTrue(any(m == 10 and n == 10 for m, n, _ in args))
        self.assertTrue(any(m != n and (n, m, k) in args for m, n, k in args))
        self.assertEqual({k for _, _, k in args}, {1, 2, 3, 4})
        labels = {case["oracle"]["feasible"] for case in cases}
        self.assertEqual(labels, {False, True})


class ExactMonotonePathsCheckerTests(unittest.TestCase):
    def check(self, actual, *, m=3, n=3, k=4, feasible=True):
        return check_exact_monotone_paths(
            actual, [m, n, k], {}, {"feasible": feasible}
        )

    def test_accepts_valid_non_unique_construction(self) -> None:
        self.assertTrue(self.check(["..#", "...", "#.."]).passed)

    def test_empty_uses_only_trusted_feasible_label(self) -> None:
        self.assertTrue(self.check([], m=1, n=5, k=2, feasible=False).passed)
        result = self.check([], feasible=True)
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_category, "unexpected_empty")

    def test_rejects_return_type_and_shape_errors(self) -> None:
        cases = [
            ("...", "invalid_return_type"),
            (["..."], "invalid_row_count"),
            ([["."] * 3 for _ in range(3)], "invalid_row_type"),
            (["..", "...", "..."], "invalid_column_count"),
            (["..x", "...", "..."], "invalid_character"),
        ]
        for actual, category in cases:
            with self.subTest(category=category):
                result = self.check(actual)
                self.assertFalse(result.passed)
                self.assertEqual(result.failure_category, category)

    def test_rejects_blocked_endpoints(self) -> None:
        start = self.check(["#..", "...", "..."])
        end = self.check(["...", "...", "..#"])
        self.assertEqual(start.failure_category, "blocked_start")
        self.assertEqual(end.failure_category, "blocked_end")

    def test_rejects_path_count_without_returning_the_count(self) -> None:
        result = self.check(["...", "...", "..."])
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_category, "path_count_mismatch")
        self.assertEqual(
            set(result.__dict__),
            {"passed", "failure_category"},
        )

    def test_valid_witness_contradicting_oracle_is_internal_error(self) -> None:
        result = self.check(["..#", "...", "#.."], feasible=False)
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_category, "oracle_contradiction")

    def test_invalid_trusted_case_is_internal_error(self) -> None:
        result = check_exact_monotone_paths([], [1, 1, 1], {}, {})
        self.assertEqual(result.failure_category, "invalid_oracle_data")


if __name__ == "__main__":
    unittest.main()
