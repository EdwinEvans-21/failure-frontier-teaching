from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ffjudge.models import ProblemSpec


class ProblemBankV4CalibrationTests(unittest.TestCase):
    def test_five_calibration_directories_have_required_static_assets(self) -> None:
        for number in (1563, 1575, 1579, 1591, 1601):
            directory = next((ROOT / "examples").glob(f"lc-{number}-*"))
            spec = ProblemSpec.load(directory / "problem.json")
            self.assertEqual(spec.entrypoint.kind, "class_method")
            self.assertGreaterEqual(len(json.loads((directory / "public_tests.json").read_text())), 5)
            self.assertGreaterEqual(len(json.loads((directory / "hidden_tests.json").read_text())), 60)
            self.assertGreaterEqual(len(json.loads((directory / "stress_tests.json").read_text())), 3)
            self.assertEqual(len(json.loads((directory / "mutants.json").read_text())), 5)

    def test_stale_calibration_dirs_are_not_present_after_regeneration(self) -> None:
        for number in (1707, 1982):
            matches = list((ROOT / "examples").glob(f"lc-{number}-*"))
            self.assertEqual(matches, [])

    def test_selected_calibration_problems_remain_exact_comparison(self) -> None:
        for number in (1563, 1575, 1579, 1591, 1601):
            directory = next((ROOT / "examples").glob(f"lc-{number}-*"))
            spec = ProblemSpec.load(directory / "problem.json")
            self.assertEqual(spec.comparison, "exact")

    def test_source_audit_verified_all_selected_problems(self) -> None:
        audit = json.loads((ROOT / "experiments/problem_bank_v4_100/problem_source_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["problem_count"], 69)
        self.assertEqual(audit["verified_count"], 69)
        self.assertEqual(audit["failed"], [])


if __name__ == "__main__":
    unittest.main()
