from __future__ import annotations

import unittest

from tools.expanded_benchmark_catalog import (
    BITS,
    DP,
    EXPANDED_BASELINE_ID,
    GRAPH,
    GREEDY,
    records,
)


EXPECTED_IDS = (
    3123, 3108, 2421, 1697, 1786, 1970, 1368, 2203,
    3117, 3077, 2188, 2809, 2478, 2719, 2945, 2926, 2035, 1547,
    2071, 1851, 2940, 3072, 2366, 3102, 3116,
    1611, 1896, 995, 3022, 3045, 761,
)


class ExpandedBenchmarkCatalogTests(unittest.TestCase):
    def test_catalog_is_exact_authoritative_order(self) -> None:
        catalog = records()
        self.assertEqual(len(catalog), 31)
        self.assertEqual(
            tuple(item["frontend_id"] for item in catalog), EXPECTED_IDS
        )
        self.assertEqual(len({item["problem_id"] for item in catalog}), 31)
        self.assertEqual(EXPANDED_BASELINE_ID,
                         "failure-frontier-baseline-v3-expanded")

    def test_metadata_is_fixed_before_model_results(self) -> None:
        catalog = records()
        self.assertEqual(
            {item["topic"] for item in catalog},
            {GRAPH, DP, GREEDY, BITS},
        )
        self.assertTrue(all(item["comparison"] == "exact" for item in catalog))
        self.assertTrue(all(item["entrypoint"].startswith("Solution.")
                            for item in catalog))
        self.assertTrue(all(item["memorization_risk"] in {"low", "medium", "high"}
                            for item in catalog))

    def test_classic_problem_risk_is_not_selected_post_hoc(self) -> None:
        high = {
            item["frontend_id"] for item in records()
            if item["memorization_risk"] == "high"
        }
        self.assertEqual(high, {1368, 1547, 1851, 1611, 995, 761, 1970, 2035})


if __name__ == "__main__":
    unittest.main()
