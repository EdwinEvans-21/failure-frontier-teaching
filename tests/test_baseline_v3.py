from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
for directory in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from baseline_v3 import BASELINE_ID, discover_frozen_paths  # noqa: E402
from verify_baseline_v3_manifest import verify  # noqa: E402


MANIFEST = ROOT / "experiments/baseline_v3/baseline_manifest.json"
V2_MANIFEST = ROOT / "experiments/baseline_v2/baseline_manifest.json"


class BaselineV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def copy_baseline(self, destination: Path) -> Path:
        for item in self.manifest["frozen_files"]:
            relative = Path(item["path"])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        target_manifest = (
            destination / "experiments/baseline_v3/baseline_manifest.json"
        )
        target_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, target_manifest)
        return target_manifest

    def test_checked_in_manifest_verifies(self) -> None:
        self.assertEqual(verify(ROOT, MANIFEST), [])
        self.assertEqual(self.manifest["baseline_id"], BASELINE_ID)

    def test_scope_is_problem_and_judge_only_with_no_readme(self) -> None:
        paths = {item["path"] for item in self.manifest["frozen_files"]}
        v2 = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(paths, {item["path"] for item in v2["frozen_files"]})
        self.assertEqual(len(paths), 33)
        self.assertFalse(
            any(Path(path).name.lower() == "readme.md" for path in paths)
        )
        self.assertNotIn("experiments/prompts/problem.md", paths)
        self.assertNotIn("experiments/pilot/orchestrator.py", paths)
        self.assertNotIn("tests/test_runner.py", paths)

    def test_readme_and_research_prompt_changes_are_not_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            readme = root / "examples/palindrome_number/README.md"
            readme.write_text("not benchmark semantics\n", encoding="utf-8")
            prompt = root / "experiments/prompts/problem.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("not frozen\n", encoding="utf-8")
            self.assertEqual(verify(root, manifest), [])

    def test_runner_change_is_detected_without_content_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            runner = root / "src/ffjudge/runner.py"
            runner.write_text(
                runner.read_text(encoding="utf-8")
                + "\n# V3_HIDDEN_SENTINEL_DO_NOT_PRINT\n",
                encoding="utf-8",
            )
            diagnostic = "\n".join(verify(root, manifest))
            self.assertIn("modified frozen file: src/ffjudge/runner.py", diagnostic)
            self.assertNotIn("V3_HIDDEN_SENTINEL_DO_NOT_PRINT", diagnostic)

    def test_timing_boundary_is_explicit(self) -> None:
        timing = self.manifest["judge_timing_policy"]
        self.assertEqual(
            timing["runtime_source"], "container_harness_monotonic_clock"
        )
        self.assertFalse(timing["docker_startup_included"])
        self.assertEqual(
            timing["docker_host_watchdog_verdict"], "INTERNAL_ERROR"
        )
        self.assertEqual(
            timing["submission_execution_timeout_verdict"],
            "TIME_LIMIT_EXCEEDED",
        )

    def test_discovery_never_includes_readme_case_variants(self) -> None:
        self.assertFalse(
            any(
                Path(path).name.lower() == "readme.md"
                for path in discover_frozen_paths(ROOT)
            )
        )


if __name__ == "__main__":
    unittest.main()
