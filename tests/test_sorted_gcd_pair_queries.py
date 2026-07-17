from itertools import combinations_with_replacement
from math import gcd
from pathlib import Path
import importlib.util
import json
import unittest

from ffjudge.models import ProblemSpec
from ffjudge.oracles.sorted_gcd_pair_queries import (
    gcd_values_bruteforce,
    gcd_values_reference,
)
from ffjudge.runner import equivalent


class SortedGcdPairQueriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = (
            Path(__file__).parents[1]
            / "examples"
            / "sorted_gcd_pair_queries"
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

    @staticmethod
    def small_multisets():
        for n in range(2, 7):
            yield from combinations_with_replacement(range(1, 9), n)

    def test_metadata_registers_hard_number_theory_problem(self) -> None:
        self.assertEqual(
            self.spec.problem_id, "lc-3312-sorted-gcd-pair-queries"
        )
        self.assertEqual(self.spec.difficulty, "hard")
        self.assertEqual(self.spec.role, "hard_number_theory_candidate")
        self.assertEqual(self.spec.comparison, "exact")
        self.assertEqual(self.spec.entrypoint.class_name, "Solution")
        self.assertEqual(self.spec.entrypoint.method, "gcdValues")
        self.assertEqual(self.spec.limits.time_seconds, 1.0)
        self.assertEqual(self.spec.limits.memory_mb, 256)

    def test_exhaustive_small_multisets_match_bruteforce(self) -> None:
        arrays = answers = 0
        for values in self.small_multisets():
            nums = list(values)
            queries = list(range(len(nums) * (len(nums) - 1) // 2))
            self.assertEqual(
                gcd_values_reference(nums, queries),
                gcd_values_bruteforce(nums, queries),
                values,
            )
            arrays += 1
            answers += len(queries)
        self.assertEqual(arrays, 2_994)
        self.assertEqual(answers, 36_036)

    def test_input_permutation_invariant(self) -> None:
        variants = 0
        for values in self.small_multisets():
            nums = list(values)
            queries = list(range(len(nums) * (len(nums) - 1) // 2))
            expected = gcd_values_reference(nums, queries)
            permutations = [nums[::-1], nums[1:] + nums[:1]]
            for permutation in permutations:
                self.assertEqual(
                    gcd_values_reference(permutation, queries), expected
                )
                variants += 1
        self.assertEqual(variants, 5_988)

    def test_query_permutation_invariant(self) -> None:
        variants = 0
        for values in self.small_multisets():
            nums = list(values)
            queries = list(range(len(nums) * (len(nums) - 1) // 2))
            expected = gcd_values_reference(nums, queries)
            permutations = [
                list(range(len(queries) - 1, -1, -1)),
                list(range(0, len(queries), 2))
                + list(range(1, len(queries), 2)),
            ]
            for order in permutations:
                permuted_queries = [queries[index] for index in order]
                self.assertEqual(
                    gcd_values_reference(nums, permuted_queries),
                    [expected[index] for index in order],
                )
                variants += 1
        self.assertEqual(variants, 5_988)

    def test_uniform_scaling_invariant(self) -> None:
        variants = 0
        for n in range(2, 6):
            for values in combinations_with_replacement(range(1, 7), n):
                nums = list(values)
                queries = list(range(n * (n - 1) // 2))
                expected = gcd_values_reference(nums, queries)
                for scale in (2, 3, 5):
                    scaled = gcd_values_reference(
                        [value * scale for value in nums], queries
                    )
                    self.assertEqual(
                        scaled, [value * scale for value in expected]
                    )
                    variants += 1
        self.assertEqual(variants, 1_365)

    def test_formal_cases_follow_contract_and_reference(self) -> None:
        self.assertEqual(len(self.public_cases), 4)
        self.assertEqual(len(self.hidden_cases), 18)
        for case in self.public_cases + self.hidden_cases:
            self.assertEqual(set(case), {"args", "expected"})
            nums, queries = case["args"]
            self.assertGreaterEqual(len(nums), 2)
            self.assertLessEqual(len(nums), 100_000)
            self.assertTrue(all(type(value) is int and 1 <= value <= 50_000
                                for value in nums))
            self.assertGreaterEqual(len(queries), 1)
            self.assertLessEqual(len(queries), 100_000)
            pair_count = len(nums) * (len(nums) - 1) // 2
            self.assertTrue(all(type(query) is int
                                and 0 <= query < pair_count
                                for query in queries))
            self.assertTrue(all(type(value) is int
                                for value in case["expected"]))
            self.assertEqual(len(case["expected"]), len(queries))
            self.assertEqual(
                case["expected"], gcd_values_reference(nums, queries)
            )

    def test_hidden_suite_covers_required_boundaries_and_families(self) -> None:
        arguments = [case["args"] for case in self.hidden_cases]
        self.assertTrue(any(len(nums) == 2 for nums, _ in arguments))
        self.assertTrue(any(set(nums) == {1} for nums, _ in arguments))
        self.assertTrue(any(len(set(nums)) == 1 for nums, _ in arguments))
        self.assertTrue(any(len(nums) - len(set(nums)) >= 50
                            for nums, _ in arguments))
        self.assertTrue(any(nums == [1, 2, 4, 8, 16, 32, 64]
                            for nums, _ in arguments))
        self.assertTrue(any(max(nums) >= 49_999 and len(nums) <= 10
                            for nums, _ in arguments))
        self.assertTrue(any(0 in queries for _, queries in arguments))
        self.assertTrue(any(
            len(nums) * (len(nums) - 1) // 2 - 1 in queries
            for nums, queries in arguments
        ))
        self.assertTrue(any(len(queries) > len(set(queries)) + 50
                            for _, queries in arguments))
        self.assertTrue(any(queries != sorted(queries)
                            for _, queries in arguments))
        self.assertEqual(sum(
            len(nums) == 100_000 or len(queries) == 100_000
            for nums, queries in arguments
        ), 3)
        self.assertTrue(any(
            len(nums) * (len(nums) - 1) // 2 > 2**31 - 1
            for nums, _ in arguments
        ))

    def test_hidden_suite_straddles_exact_gcd_count_boundaries(self) -> None:
        nums, queries = self.hidden_cases[9]["args"]
        pairs = sorted(
            gcd(nums[left], nums[right])
            for left in range(len(nums))
            for right in range(left + 1, len(nums))
        )
        boundaries = [
            index for index in range(1, len(pairs))
            if pairs[index - 1] != pairs[index]
        ]
        self.assertTrue(boundaries)
        for boundary in boundaries:
            for query in (boundary - 1, boundary, boundary + 1):
                if query < len(pairs):
                    self.assertIn(query, queries)

    def test_reference_submission_passes_every_formal_case(self) -> None:
        solution = self.load_solution(self.fixture_root / "accepted.py")
        for case in self.public_cases + self.hidden_cases:
            actual = solution.gcdValues(*case["args"])
            self.assertTrue(equivalent(actual, case["expected"], self.spec))

    def test_wrong_answer_submissions_are_deterministically_caught(self) -> None:
        cases = self.public_cases + self.hidden_cases
        for filename in (
            "wrong_no_inclusion_exclusion.py",
            "wrong_binary_search_boundary.py",
        ):
            solution = self.load_solution(self.fixture_root / filename)
            with self.subTest(submission=filename):
                self.assertTrue(any(
                    not equivalent(
                        solution.gcdValues(*case["args"]),
                        case["expected"],
                        self.spec,
                    )
                    for case in cases
                ))

    def test_pair_enumerator_is_correct_on_small_cases_but_has_stress_case(self) -> None:
        solution = self.load_solution(
            self.fixture_root / "wrong_enumerate_pairs.py"
        )
        for case in self.public_cases + self.hidden_cases[:15]:
            self.assertEqual(
                solution.gcdValues(*case["args"]), case["expected"]
            )
        self.assertTrue(any(
            len(case["args"][0]) == 100_000 for case in self.hidden_cases
        ))

    def test_statement_omits_removed_special_instruction(self) -> None:
        statement = (self.fixture_root / "README.md").read_text(
            encoding="utf-8"
        )
        removed_name = "lafor" + "vinda"
        self.assertNotIn(removed_name, statement.casefold())


if __name__ == "__main__":
    unittest.main()
