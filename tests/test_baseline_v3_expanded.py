from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]
for directory in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from baseline_v3_expanded import (  # noqa: E402
    BASELINE_ID,
    discover_frozen_paths,
    expanded_problem_records,
)
from experiments.pilot.config import load_config  # noqa: E402


MANIFEST = ROOT / "experiments/baseline_v3_expanded/baseline_manifest.json"
CONFIG = ROOT / "experiments/configs/expanded_exploratory_v1.yaml"


class ExpandedBaselineSourceTests(unittest.TestCase):
    def test_scope_has_31_problems_and_no_readme(self) -> None:
        paths = discover_frozen_paths(ROOT)
        self.assertEqual(len(expanded_problem_records(ROOT)), 31)
        self.assertEqual(sum(Path(path).name.lower() == "readme.md" for path in paths), 0)
        self.assertEqual(len(paths), 355)

    def test_expanded_config_is_exactly_the_authoritative_order(self) -> None:
        config = load_config(CONFIG)
        self.assertEqual(config.baseline_id, BASELINE_ID)
        self.assertEqual(len(config.problems), 31)
        ids = [
            json.loads((ROOT / item.problem).read_text(encoding="utf-8"))["problem_id"]
            for item in config.problems
        ]
        expected = [item["fixture"] for item in expanded_problem_records(ROOT)]
        self.assertEqual(ids, expected)
        self.assertFalse(config.model.reasoning_mode)
        self.assertEqual(config.model.thinking, {"type": "disabled"})

    @unittest.skipUnless(MANIFEST.is_file(), "manifest-only commit not generated yet")
    def test_checked_in_expanded_manifest_identity(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["baseline_id"], BASELINE_ID)
        self.assertEqual(manifest["scope_summary"]["frozen_file_count"], 355)
        self.assertEqual(manifest["scope_summary"]["readme_frozen_count"], 0)


if __name__ == "__main__":
    unittest.main()
