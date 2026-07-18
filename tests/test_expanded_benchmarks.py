from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ffjudge.models import ProblemSpec
from tools.expanded_benchmark_catalog import records
from tools.expanded_benchmark_specs import SPECS


ROOT = Path(__file__).resolve().parents[1]


def _load_solution(path: Path):
    namespace = {"__name__": "fixture_" + hashlib.sha256(str(path).encode()).hexdigest()}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace["Solution"]()


class ExpandedBenchmarkTests(unittest.TestCase):
    def test_all_31_canonical_fixtures_are_complete(self) -> None:
        for record in records():
            fixture = ROOT / "examples" / str(record["problem_id"])
            with self.subTest(problem=record["problem_id"]):
                self.assertTrue(fixture.is_dir())
                self.assertEqual(
                    {"problem.json", "benchmark_metadata.json", "public_tests.json", "hidden_tests.json",
                     "stress_tests.json", "accepted.py", "mutants.json",
                     "wrong_boundary.py", "wrong_off_by_one.py", "wrong_direction.py"},
                    {path.name for path in fixture.iterdir() if path.is_file()})
                problem = ProblemSpec.load(fixture / "problem.json")
                self.assertEqual(problem.problem_id, record["problem_id"])
                self.assertEqual(problem.entrypoint.method, record["method"])
                self.assertEqual(problem.comparison, "exact")
                metadata = json.loads((fixture / "benchmark_metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(metadata["memorization_risk"], record["memorization_risk"])
                self.assertEqual(metadata["generator_seed"], 20260718)
                self.assertIn("Python", problem.output_contract)
                self.assertGreater(len(problem.description), 100)
                public = json.loads((fixture / "public_tests.json").read_text(encoding="utf-8"))
                hidden = json.loads((fixture / "hidden_tests.json").read_text(encoding="utf-8"))
                stress = json.loads((fixture / "stress_tests.json").read_text(encoding="utf-8"))
                self.assertGreaterEqual(len(hidden), 10)
                self.assertLessEqual(len(hidden), 20)
                self.assertGreaterEqual(len(stress), 3)
                self.assertLessEqual(len(stress), 5)
                public_keys = {json.dumps(case["args"], sort_keys=True) for case in public}
                hidden_keys = {json.dumps(case["args"], sort_keys=True) for case in hidden}
                stress_keys = {json.dumps(case["args"], sort_keys=True) for case in stress}
                self.assertEqual(len(hidden_keys), len(hidden))
                self.assertEqual(len(stress_keys), len(stress))
                self.assertTrue(public_keys.isdisjoint(hidden_keys))
                self.assertTrue(public_keys.isdisjoint(stress_keys))
                self.assertTrue(hidden_keys.isdisjoint(stress_keys))

    def test_reference_expected_is_independently_cross_checked_on_formal_small_cases(self) -> None:
        for record in records():
            frontend_id = int(record["frontend_id"])
            _reference, brute, _examples, _description = SPECS[frontend_id]
            fixture = ROOT / "examples" / str(record["problem_id"])
            cases = json.loads((fixture / "public_tests.json").read_text(encoding="utf-8"))
            cases += json.loads((fixture / "hidden_tests.json").read_text(encoding="utf-8"))
            for index, case in enumerate(cases):
                with self.subTest(problem=record["problem_id"], case=index):
                    self.assertEqual(brute(*copy.deepcopy(case["args"])), case["expected"])

    def test_standalone_accepted_passes_all_formal_suites(self) -> None:
        for record in records():
            fixture = ROOT / "examples" / str(record["problem_id"])
            solution = _load_solution(fixture / "accepted.py")
            method = getattr(solution, str(record["method"]))
            for suite in ("public_tests.json", "hidden_tests.json", "stress_tests.json"):
                cases = json.loads((fixture / suite).read_text(encoding="utf-8"))
                for index, case in enumerate(cases):
                    with self.subTest(problem=record["problem_id"], suite=suite, case=index):
                        self.assertEqual(method(*copy.deepcopy(case["args"])), case["expected"])

    def test_every_declared_mutant_is_stably_killed_by_non_stress_tests(self) -> None:
        for record in records():
            fixture = ROOT / "examples" / str(record["problem_id"])
            cases = json.loads((fixture / "public_tests.json").read_text(encoding="utf-8"))
            cases += json.loads((fixture / "hidden_tests.json").read_text(encoding="utf-8"))
            declared = json.loads((fixture / "mutants.json").read_text(encoding="utf-8"))
            for filename in declared:
                solution = _load_solution(fixture / filename)
                method = getattr(solution, str(record["method"]))
                killed = [index for index, case in enumerate(cases)
                          if method(*copy.deepcopy(case["args"])) != case["expected"]]
                with self.subTest(problem=record["problem_id"], mutant=filename):
                    self.assertTrue(killed)

    def test_generator_is_byte_identical_in_temporary_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "examples"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "generate_expanded_benchmarks.py"),
                 "--output-root", str(output)], cwd=ROOT, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for record in records():
                expected = ROOT / "examples" / str(record["problem_id"])
                actual = output / str(record["problem_id"])
                self.assertEqual(
                    {p.name: p.read_bytes() for p in expected.iterdir() if p.is_file()},
                    {p.name: p.read_bytes() for p in actual.iterdir() if p.is_file()},
                    record["problem_id"])


if __name__ == "__main__":
    unittest.main()
