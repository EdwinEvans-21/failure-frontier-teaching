from contextlib import redirect_stderr
from pathlib import Path
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from generate_baseline_manifest import (  # noqa: E402
    BASELINE_ID,
    build_manifest,
    canonical_json_bytes,
    source_worktree_changes,
)
from verify_baseline_manifest import verify  # noqa: E402


class BaselineManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = (
            ROOT / "experiments" / "baseline_v1" / "baseline_manifest.json"
        )
        cls.manifest = json.loads(cls.manifest_path.read_text(encoding="utf-8"))

    def copy_baseline(self, destination: Path) -> Path:
        for record in self.manifest["frozen_files"]:
            relative = Path(record["path"])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        manifest = destination / "experiments/baseline_v1/baseline_manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.manifest_path, manifest)
        return manifest

    def verify_copy(self, mutate=None) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.copy_baseline(root)
            if mutate is not None:
                mutate(root)
            return verify(root, manifest)

    def test_checked_in_baseline_verifies(self) -> None:
        self.assertEqual(verify(ROOT, self.manifest_path), [])

    def test_manifest_identity_and_environment_are_recorded(self) -> None:
        self.assertEqual(self.manifest["baseline_id"], BASELINE_ID)
        self.assertEqual(self.manifest["schema_version"], "1.0")
        environment = self.manifest["environment"]
        for field in (
            "python_version",
            "docker_client_version",
            "docker_server_version",
            "ffjudge_image_id",
            "base_image_repo_digest",
            "source_commit",
            "source_worktree_dirty",
            "dirty_ignored_paths",
        ):
            self.assertIn(field, environment)

    def test_frozen_content_change_fails(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "pyproject.toml"
            path.write_text(
                path.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )

        errors = self.verify_copy(mutate)
        self.assertTrue(any("modified frozen file: pyproject.toml" in error
                            for error in errors))

    def test_missing_frozen_file_fails(self) -> None:
        def mutate(root: Path) -> None:
            (root / "experiments/baseline_v1/initial_prompt.template.md").unlink()

        errors = self.verify_copy(mutate)
        self.assertTrue(any("missing frozen file:" in error for error in errors))

    def test_new_file_in_frozen_scope_fails(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "examples/palindrome_number/unregistered.py"
            path.write_text("value = 1\n", encoding="utf-8")

        errors = self.verify_copy(mutate)
        self.assertTrue(any("new frozen-scope file:" in error for error in errors))

    def test_non_frozen_file_change_is_ignored(self) -> None:
        def mutate(root: Path) -> None:
            (root / "research_notes.tmp").write_text("not frozen", encoding="utf-8")

        self.assertEqual(self.verify_copy(mutate), [])

    def test_problem_configuration_drift_is_reported(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "examples/palindrome_number/problem.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["entrypoint"]["method"] = "changedMethod"
            path.write_text(json.dumps(value), encoding="utf-8")

        errors = self.verify_copy(mutate)
        self.assertTrue(any(
            "problem configuration drift: palindrome_number.entrypoint" in error
            for error in errors
        ))

    def test_hidden_file_failure_does_not_emit_hidden_content(self) -> None:
        sentinel = "SECRET-HIDDEN-VALUE-DO-NOT-PRINT"

        def mutate(root: Path) -> None:
            path = root / "examples/palindrome_number/hidden_tests.json"
            cases = json.loads(path.read_text(encoding="utf-8"))
            cases[0]["expected"] = sentinel
            path.write_text(json.dumps(cases), encoding="utf-8")

        errors = self.verify_copy(mutate)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            for error in errors:
                print(error, file=sys.stderr)
        diagnostic = stderr.getvalue()
        self.assertIn("hidden_tests.json", diagnostic)
        self.assertNotIn(sentinel, diagnostic)
        self.assertNotIn(str(self.manifest["problems"]), diagnostic)

    def test_json_hash_ignores_formatting_and_line_endings(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "examples/palindrome_number/problem.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            rendered = json.dumps(value, ensure_ascii=False, indent=4)
            path.write_bytes(rendered.replace("\n", "\r\n").encode("utf-8"))

        self.assertEqual(self.verify_copy(mutate), [])

    def test_text_hash_ignores_only_line_ending_style(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "examples/palindrome_number/README.md"
            text = path.read_text(encoding="utf-8")
            path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))

        self.assertEqual(self.verify_copy(mutate), [])

    def test_generator_determinism_metadata_has_no_unseeded_randomness(self) -> None:
        records = self.manifest["formal_test_generators"]
        self.assertFalse(any(record["deterministic"] is False for record in records))
        record = next(
            item for item in records
            if item["fixture"] == "maximum_subarray_sum_after_k_swaps"
        )
        self.assertEqual(record["random_seed"], 3962)
        for item in records:
            if item["path"] is not None:
                self.assertEqual(
                    item["temporary_regeneration"]["result"],
                    "byte_identical",
                )

    def test_dirty_check_ignores_manifest_and_docker_log_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True,
                           capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "baseline@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Baseline Test"],
                cwd=root,
                check=True,
            )
            manifest = root / "experiments/baseline_v1/baseline_manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}\n", encoding="utf-8")
            source = root / "source.py"
            source.write_text("value = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                "docker-full-test.log\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            manifest.write_text('{"generated":true}\n', encoding="utf-8")
            (root / "docker-full-test.log").write_text("ignored", encoding="utf-8")
            self.assertEqual(source_worktree_changes(root), [])
            source.write_text("value = 2\n", encoding="utf-8")
            self.assertEqual(source_worktree_changes(root), ["source.py"])

    def test_rebuilding_manifest_preserves_frozen_problem_metadata(self) -> None:
        rebuilt = build_manifest(ROOT, created_at=self.manifest["created_at"])
        self.assertEqual(rebuilt["problems"], self.manifest["problems"])
        fields = ("fixture", "path", "deterministic", "random_seed", "check")
        self.assertEqual(
            [{field: item.get(field) for field in fields}
             for item in rebuilt["formal_test_generators"]],
            [{field: item.get(field) for field in fields}
             for item in self.manifest["formal_test_generators"]],
        )

    def test_canonical_json_keeps_array_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text('[{"a":1},{"a":2}]', encoding="utf-8")
            second.write_text('[{"a":2},{"a":1}]', encoding="utf-8")
            self.assertNotEqual(
                canonical_json_bytes(first), canonical_json_bytes(second)
            )


if __name__ == "__main__":
    unittest.main()
