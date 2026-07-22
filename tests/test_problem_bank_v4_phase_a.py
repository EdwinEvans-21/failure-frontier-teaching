from __future__ import annotations

from pathlib import Path
import json
import unittest

from tools.audit_lc_problem_bank_v4 import OUTPUT, scan
from tools.lc_problem_bank_v4_catalog import FIXED_PROBLEMS, problem_id


class ProblemBankV4PhaseATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = scan()

    def test_only_directory_prefix_lc_is_counted(self) -> None:
        self.assertEqual(self.audit["lc_count_before"], 31)
        self.assertEqual(self.audit["non_lc_count"], 5)
        self.assertTrue(all(name.startswith("lc-") for name in self.audit["lc_directories"]))
        self.assertTrue(all(not name.startswith("lc-") for name in self.audit["non_lc_directories"]))

    def test_selection_is_exactly_69_and_final_union_is_100(self) -> None:
        selected = self.audit["selected_new_problems"]
        self.assertEqual(len(FIXED_PROBLEMS), 69)
        self.assertEqual(len(selected), 69)
        identifiers = self.audit["lc_directories"] + [row["problem_id"] for row in selected]
        self.assertEqual(len(identifiers), 100)
        self.assertEqual(len(set(identifiers)), 100)
        numbers = [int(identifier.split("-", 2)[1]) for identifier in identifiers]
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_required_replacements_are_deterministic(self) -> None:
        self.assertEqual(
            self.audit["replacements"],
            [
                {
                    "fixed_problem_id": "lc-1547-minimum-cost-to-cut-a-stick",
                    "status": "ALREADY_PRESENT",
                    "replacement_problem_id": "lc-2334-subarray-with-elements-greater-than-varying-threshold",
                },
                {
                    "fixed_problem_id": "lc-2035-partition-array-into-two-arrays-to-minimize-sum-difference",
                    "status": "ALREADY_PRESENT",
                    "replacement_problem_id": "lc-2338-count-the-number-of-ideal-arrays",
                },
                {
                    "fixed_problem_id": "lc-2188-minimum-time-to-finish-the-race",
                    "status": "ALREADY_PRESENT",
                    "replacement_problem_id": "lc-2360-longest-cycle-in-a-graph",
                },
            ],
        )

    def test_all_legacy_problems_need_v4_supplements(self) -> None:
        gaps = self.audit["legacy_quality_gaps"]
        self.assertEqual(len(gaps), 31)
        self.assertTrue(all(row["v4_supplement_required"] for row in gaps))

    def test_phase_a_artifacts_match_live_scan(self) -> None:
        persisted = json.loads((OUTPUT / "phase_a_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted, self.audit)
        snapshot = json.loads((OUTPUT / "legacy_lc_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["file_count"], 310)
        self.assertEqual(snapshot["files"], self.audit["legacy_file_sha256"])


if __name__ == "__main__":
    unittest.main()
