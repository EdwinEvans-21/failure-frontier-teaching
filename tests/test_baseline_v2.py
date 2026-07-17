from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import io
import json
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
for directory in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from baseline_v2 import BASELINE_ID, discover_frozen_paths  # noqa: E402
from verify_baseline_v2_manifest import verify  # noqa: E402
from audit_problem_statements import audit  # noqa: E402
from experiments.pilot.prompts import PromptRenderer  # noqa: E402


MANIFEST = ROOT / "experiments/baseline_v2/baseline_manifest.json"
AUDIT = ROOT / "experiments/baseline_v2/problem_statement_audit.json"
SNAPSHOTS = ROOT / "experiments/baseline_v2/rendered_prompt_snapshots.json"
CONFIG = ROOT / "experiments/configs/pilot_v1.yaml"
EXPECTED_V2_SUPERSEDED_DRIFT = [
    "modified frozen file: src/ffjudge/runner.py"
]


class BaselineV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def copy_baseline(self, destination: Path) -> Path:
        for item in self.manifest["frozen_files"]:
            relative = Path(item["path"])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        target_manifest = destination / "experiments/baseline_v2/baseline_manifest.json"
        target_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, target_manifest)
        return target_manifest

    def test_v2_is_preserved_and_superseded_only_by_runner_timing(self) -> None:
        self.assertEqual(verify(ROOT, MANIFEST), EXPECTED_V2_SUPERSEDED_DRIFT)
        self.assertEqual(self.manifest["baseline_id"], BASELINE_ID)

    def test_no_readme_case_variant_is_frozen(self) -> None:
        paths = [Path(item["path"]) for item in self.manifest["frozen_files"]]
        self.assertFalse(any(path.name.lower() == "readme.md" for path in paths))
        self.assertFalse(any(Path(path).name.lower() == "readme.md"
                             for path in discover_frozen_paths(ROOT)))

    def test_readme_changes_and_deletion_do_not_affect_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            for variant in ("README.md", "Readme.md", "readme.md"):
                path = root / "examples/palindrome_number" / variant
                path.write_text("arbitrary human documentation\n", encoding="utf-8")
            self.assertEqual(
                verify(root, manifest), EXPECTED_V2_SUPERSEDED_DRIFT
            )
            for path in (root / "examples/palindrome_number").glob("*eadme.md"):
                path.unlink()
            self.assertEqual(
                verify(root, manifest), EXPECTED_V2_SUPERSEDED_DRIFT
            )

    def test_problem_json_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            path = root / "examples/minimum_operations_binary_transform/problem.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["description"] += " changed"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = verify(root, manifest)
            self.assertTrue(any("modified frozen file:" in error for error in errors))

    def test_public_hidden_oracle_and_judge_changes_fail_without_leaks(self) -> None:
        mutations = (
            "examples/palindrome_number/public_tests.json",
            "examples/palindrome_number/hidden_tests.json",
            "src/ffjudge/oracles/minimum_operations_binary_transform.py",
            "src/ffjudge/runner.py",
        )
        for relative in mutations:
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = self.copy_baseline(root)
                path = root / relative
                if path.suffix == ".json":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data[0]["v2_secret_sentinel"] = "DO_NOT_PRINT_THIS_VALUE"
                    path.write_text(json.dumps(data), encoding="utf-8")
                else:
                    path.write_text(path.read_text(encoding="utf-8") + "\n# drift\n",
                                    encoding="utf-8")
                errors = verify(root, manifest)
                diagnostic = "\n".join(errors)
                self.assertIn("modified frozen file:", diagnostic)
                self.assertNotIn("DO_NOT_PRINT_THIS_VALUE", diagnostic)

    def test_manifest_with_readme_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["frozen_files"].append({
                "path": "examples/palindrome_number/Readme.md",
                "category": "invalid",
                "sha256": "0" * 64,
                "hash_mode": "utf8_normalized_lf_v1",
            })
            manifest.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("README.md entered the v2 frozen scope", verify(root, manifest))


class ProblemStatementIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.renderer = PromptRenderer(ROOT / "experiments/prompts")
        cls.snapshots = json.loads(SNAPSHOTS.read_text(encoding="utf-8"))["snapshots"]

    def rendered(self, item: dict[str, str]) -> str:
        return self.renderer.formatted_problem(
            ROOT / item["problem"], ROOT / item["public_tests"]
        )

    def test_five_problem_audit_has_no_unresolved_findings(self) -> None:
        self.assertEqual(audit(ROOT), [])
        records = json.loads(AUDIT.read_text(encoding="utf-8"))["records"]
        self.assertEqual(len(records), 5)
        self.assertTrue(all(not item["missing_information"] for item in records))
        self.assertTrue(all(not item["semantic_inconsistencies"] for item in records))

    def test_all_rendered_prompts_match_exact_snapshots(self) -> None:
        for item in self.config["problems"]:
            rendered = self.rendered(item)
            spec = json.loads((ROOT / item["problem"]).read_text(encoding="utf-8"))
            snapshot = self.snapshots[spec["problem_id"]]
            self.assertEqual(len(rendered), snapshot["length"])
            self.assertEqual(sha256(rendered.encode("utf-8")).hexdigest(),
                             snapshot["sha256"])

    def test_renderer_reads_only_problem_public_tests_and_problem_template(self) -> None:
        item = self.config["problems"][2]
        reads: list[Path] = []
        original = Path.read_text

        def tracked(path: Path, *args, **kwargs):
            reads.append(path.resolve())
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked):
            self.rendered(item)
        allowed = {
            (ROOT / item["problem"]).resolve(),
            (ROOT / item["public_tests"]).resolve(),
            (ROOT / "experiments/prompts/problem.md").resolve(),
        }
        self.assertEqual(set(reads), allowed)
        self.assertFalse(any(path.name.lower() == "readme.md" for path in reads))
        self.assertFalse(any(path.name == "hidden_tests.json" for path in reads))
        self.assertFalse(any("oracles" in path.parts for path in reads))

    def test_readme_modification_or_removal_does_not_change_rendering(self) -> None:
        source = ROOT / "examples/minimum_operations_binary_transform"
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for name in ("problem.json", "public_tests.json", "README.md"):
                shutil.copy2(source / name, fixture / name)
            before = self.renderer.formatted_problem(
                fixture / "problem.json", fixture / "public_tests.json")
            (fixture / "README.md").write_text(
                "contradictory sentinel documentation", encoding="utf-8")
            after_change = self.renderer.formatted_problem(
                fixture / "problem.json", fixture / "public_tests.json")
            (fixture / "README.md").unlink()
            after_delete = self.renderer.formatted_problem(
                fixture / "problem.json", fixture / "public_tests.json")
            self.assertEqual(before, after_change)
            self.assertEqual(before, after_delete)

    def test_binary_transform_operations_are_structurally_complete(self) -> None:
        rendered = self.rendered(self.config["problems"][2])
        self.assertIn("choose one position whose current bit is 0", rendered)
        self.assertIn("change that bit from 0 to 1", rendered)
        self.assertIn("two adjacent positions whose current bits are both 1", rendered)
        self.assertIn("change that adjacent pair from 11 to 00", rendered)
        self.assertIn("Each application of either operation costs one operation", rendered)
        self.assertIn("operations may be applied repeatedly", rendered)
        self.assertIn("never 00 to 11", rendered)
        self.assertIn("-1 if s2 is unreachable", rendered)

    def test_entrypoint_constraints_and_every_public_example_are_rendered(self) -> None:
        for item in self.config["problems"]:
            rendered = self.rendered(item)
            spec = json.loads((ROOT / item["problem"]).read_text(encoding="utf-8"))
            public = json.loads((ROOT / item["public_tests"]).read_text(encoding="utf-8"))
            self.assertIn(spec["input_contract"], rendered)
            self.assertIn(spec["entrypoint"]["method"], rendered)
            self.assertIn(f"Time limit: {spec['limits']['time_seconds']}s", rendered)
            self.assertIn(f"memory limit: {spec['limits']['memory_mb']} MB", rendered)
            self.assertEqual(rendered.count("Example "), len(public))


if __name__ == "__main__":
    unittest.main()
