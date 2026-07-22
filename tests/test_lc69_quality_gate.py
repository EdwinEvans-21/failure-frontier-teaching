from __future__ import annotations

import unittest
import copy
import hashlib
import json
from pathlib import Path

from src.ffjudge.oracles.lc69_independent import ORACLES, ORACLE_METADATA
from tools.audit_lc69_quality import PACK_NUMBERS, imported_directories, report
from tools.run_lc69_oracle_audit import audit


class Lc69ImportQualityGateTests(unittest.TestCase):
    def test_pack_import_has_exactly_69_directories(self) -> None:
        self.assertEqual(len(imported_directories()), 69)
        self.assertEqual(set(imported_directories()), set(PACK_NUMBERS))

    def test_every_import_has_a_documented_independent_oracle(self) -> None:
        required = {"oracle_version", "oracle_algorithm", "safe_input_bounds",
                    "exhaustive_bounds", "random_bounds", "known_limitations"}
        self.assertEqual(set(ORACLES), set(PACK_NUMBERS))
        self.assertEqual(set(ORACLE_METADATA), set(PACK_NUMBERS))
        for number, metadata in ORACLE_METADATA.items():
            with self.subTest(number=number):
                self.assertEqual(set(metadata), required)
                self.assertTrue(all(isinstance(value, str) and value for value in metadata.values()))

    def test_quality_gate_is_fail_closed_until_full_hardening(self) -> None:
        result = report()
        self.assertFalse(result["passed"])
        self.assertEqual(result["independent_oracle_count"], len(ORACLES))
        self.assertEqual(result["missing_independent_oracles"], [])
        self.assertEqual(result["missing_oracle_metadata"], [])
        self.assertTrue(result["missing_semantic_mutants"])
        self.assertTrue(result["missing_docker_max_constraint_evidence"])

    def test_first_import_batch_independent_oracles(self) -> None:
        cases = {
            1143: (['abc', 'ac'], 2),
            1155: ([2, 6, 7], 6),
            1187: ([[1, 5, 3, 6, 7], [1, 3, 2, 4]], 1),
            1220: ([2], 10),
            1235: ([[1, 2, 3], [2, 3, 4], [50, 10, 40]], 100),
            1240: ([2, 3], 3),
            1269: ([3, 2], 4),
            1278: (['abc', 2], 1),
            1284: ([[[0, 0], [0, 1]]], 3),
            1293: ([[[0, 1, 1], [1, 1, 1], [1, 0, 0]], 1], -1),
            1301: ([['E23', '2X2', '12S']], [7, 1]),
            1312: (['mbadm'], 2),
            1335: ([[6, 5, 4, 3, 2, 1], 2], 7),
            1349: ([[['.', '#', '.', '#'], ['.', '.', '#', '.'], ['#', '.', '.', '.']]], 4),
            1354: ([[9, 3, 5]], True),
            1388: ([[1, 2, 3, 4, 5, 6]], 10),
            1402: ([[-1, -8, 0, 5, -9]], 14),
            1416: (['1317', 2000], 8),
            1420: ([2, 3, 1], 6),
            1434: ([[[3, 4], [4, 5], [5]]], 1),
        }
        for number, (args, expected) in cases.items():
            with self.subTest(number=number):
                self.assertEqual(ORACLES[number](*args), expected)

    def test_differential_audit_smoke_is_multiseed_and_fail_closed(self) -> None:
        for number in (1143, 1155):
            result = audit(number, 10)
            with self.subTest(number=number):
                self.assertEqual(result["generated_count"], 100)
                self.assertEqual(len(result["seed"]), 10)
                self.assertEqual(result["mismatches"], 0)
                self.assertTrue(result["passed"])

    def test_first_semantic_mutant_batches_are_stably_killed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for directory in ("lc-1143-longest-common-subsequence", "lc-1155-number-of-dice-rolls-with-target-sum"):
            fixture = root / "examples" / directory
            cases = json.loads((fixture / "public_tests.json").read_text(encoding="utf-8"))
            cases += json.loads((fixture / "hidden_tests.json").read_text(encoding="utf-8"))
            declared = json.loads((fixture / "mutants.json").read_text(encoding="utf-8"))
            semantic = [name for name, description in declared.items() if "semantic" in description]
            self.assertGreaterEqual(len(semantic), 5)
            problem = json.loads((fixture / "problem.json").read_text(encoding="utf-8"))
            for filename in semantic:
                namespace = {"__name__": hashlib.sha256(filename.encode()).hexdigest()}
                path = fixture / filename
                exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
                method = getattr(namespace["Solution"](), problem["entrypoint"]["method"])
                with self.subTest(problem=directory, mutant=filename):
                    self.assertTrue(any(method(*copy.deepcopy(case["args"])) != case["expected"]
                                        for case in cases))


if __name__ == "__main__":
    unittest.main()
