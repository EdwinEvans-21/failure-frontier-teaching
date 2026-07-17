from itertools import product
from pathlib import Path
import importlib.util
import json
import unittest

from ffjudge.models import ProblemSpec
from ffjudge.oracles.minimum_operations_binary_transform import (
    bfs_distances,
    min_operations_reference,
)
from ffjudge.runner import equivalent


class MinimumOperationsBinaryTransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = (
            Path(__file__).parents[1]
            / "examples"
            / "minimum_operations_binary_transform"
        )
        cls.spec = ProblemSpec.load(cls.fixture_root / "problem.json")
        cls.public_cases = json.loads(
            (cls.fixture_root / "public_tests.json").read_text(encoding="utf-8")
        )
        cls.hidden_cases = json.loads(
            (cls.fixture_root / "hidden_tests.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def states(n: int) -> list[str]:
        return ["".join(bits) for bits in product("01", repeat=n)]

    @staticmethod
    def load_solution(path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Solution()

    def test_metadata_registers_medium_dp_exact_problem(self) -> None:
        self.assertEqual(
            self.spec.problem_id,
            "lc-3980-minimum-operations-binary-transform",
        )
        self.assertEqual(self.spec.role, "medium_dp_candidate")
        self.assertEqual(self.spec.comparison, "exact")
        self.assertEqual(self.spec.entrypoint.class_name, "Solution")
        self.assertEqual(self.spec.entrypoint.method, "minOperations")
        self.assertEqual(self.spec.limits.time_seconds, 1.0)
        self.assertEqual(self.spec.limits.memory_mb, 64)

    def test_bfs_oracle_matches_reference_for_every_pair_through_n_8(self) -> None:
        checked = 0
        for n in range(1, 9):
            states = self.states(n)
            for s1 in states:
                distances = bfs_distances(s1)
                for s2 in states:
                    expected = distances.get(s2, -1)
                    actual = min_operations_reference(s1, s2)
                    if actual != expected:
                        self.fail(
                            f"differential mismatch for n={n}: "
                            f"{s1!r} -> {s2!r}, {actual} != {expected}"
                        )
                    checked += 1
        self.assertEqual(checked, 87_380)

    def test_reversal_invariant_for_every_pair_through_n_8(self) -> None:
        checked = 0
        for n in range(1, 9):
            states = self.states(n)
            for s1 in states:
                for s2 in states:
                    self.assertEqual(
                        min_operations_reference(s1, s2),
                        min_operations_reference(s1[::-1], s2[::-1]),
                    )
                    checked += 1
        self.assertEqual(checked, 87_380)

    def test_identity_invariant_for_every_string_through_n_8(self) -> None:
        checked = 0
        for n in range(1, 9):
            for state in self.states(n):
                self.assertEqual(min_operations_reference(state, state), 0)
                checked += 1
        self.assertEqual(checked, 510)

    def test_formal_cases_follow_contract_and_trusted_reference(self) -> None:
        self.assertEqual(len(self.public_cases), 4)
        self.assertEqual(len(self.hidden_cases), 24)
        for case in self.public_cases + self.hidden_cases:
            self.assertEqual(set(case), {"args", "expected"})
            self.assertEqual(len(case["args"]), 2)
            s1, s2 = case["args"]
            self.assertEqual(len(s1), len(s2))
            self.assertGreaterEqual(len(s1), 1)
            self.assertLessEqual(len(s1), 100_000)
            self.assertLessEqual(set(s1 + s2), {"0", "1"})
            self.assertIs(type(case["expected"]), int)
            self.assertEqual(
                case["expected"], min_operations_reference(s1, s2)
            )

    def test_hidden_suite_has_length_one_and_linear_stress_coverage(self) -> None:
        pairs = [tuple(case["args"]) for case in self.hidden_cases]
        length_one = {(s1, s2) for s1, s2 in pairs if len(s1) == 1}
        self.assertEqual(
            length_one,
            {("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")},
        )
        self.assertTrue(any(s1 == s2 for s1, s2 in pairs))
        self.assertTrue(any(set(s1) == {"0"} and set(s2) == {"1"}
                            for s1, s2 in pairs))
        self.assertTrue(any(set(s1) == {"1"} and set(s2) == {"0"}
                            for s1, s2 in pairs))
        self.assertTrue(any(s1.startswith("01") and s2.startswith("10")
                            for s1, s2 in pairs))
        self.assertTrue(any(len(s1) == 100_000 for s1, _ in pairs))
        self.assertTrue(any(case["expected"] == -1
                            for case in self.hidden_cases))
        self.assertTrue(any(case["expected"] >= 0
                            for case in self.hidden_cases))

    def test_public_and_hidden_inputs_do_not_overlap(self) -> None:
        public = {tuple(case["args"]) for case in self.public_cases}
        hidden = {tuple(case["args"]) for case in self.hidden_cases}
        self.assertTrue(public.isdisjoint(hidden))

    def test_reference_submission_passes_all_formal_cases(self) -> None:
        solution = self.load_solution(self.fixture_root / "accepted.py")
        for case in self.public_cases + self.hidden_cases:
            actual = solution.minOperations(*case["args"])
            self.assertTrue(equivalent(actual, case["expected"], self.spec))

    def test_representative_wrong_submissions_are_caught(self) -> None:
        cases = self.public_cases + self.hidden_cases
        for filename in (
            "wrong_hamming_distance.py",
            "wrong_original_pairs_only.py",
            "wrong_nonoverlapping_greedy.py",
        ):
            with self.subTest(submission=filename):
                solution = self.load_solution(self.fixture_root / filename)
                self.assertTrue(any(
                    not equivalent(
                        solution.minOperations(*case["args"]),
                        case["expected"],
                        self.spec,
                    )
                    for case in cases
                ))


if __name__ == "__main__":
    unittest.main()
