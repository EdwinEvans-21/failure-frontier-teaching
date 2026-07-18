from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import unittest

from ffjudge.models import Verdict
from ffjudge.runner import DockerJudge
from tools.expanded_benchmark_catalog import records


RUN_DOCKER = os.environ.get("FFJUDGE_RUN_DOCKER_TESTS") == "1"


@unittest.skipUnless(RUN_DOCKER and shutil.which("docker"),
                     "set FFJUDGE_RUN_DOCKER_TESTS=1 on a machine with Docker")
class ExpandedDockerEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.judge = DockerJudge()
        cls.judge.build_image(cls.root)

    def tearDown(self) -> None:
        completed = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=^ffjudge-",
             "--format", "{{.Names}}"], capture_output=True, text=True,
            timeout=10, check=True)
        self.assertEqual(completed.stdout.strip(), "")

    def test_all_31_references_pass_public_hidden_and_stress(self) -> None:
        for record in records():
            fixture = self.root / "examples" / str(record["problem_id"])
            for suite, phase in (("public_tests.json", "public"),
                                 ("hidden_tests.json", "hidden"),
                                 ("stress_tests.json", "hidden")):
                with self.subTest(problem=record["problem_id"], suite=suite):
                    result = self.judge.judge(
                        fixture / "accepted.py", fixture / "problem.json",
                        fixture / suite, phase=phase)
                    self.assertIs(result.verdict, Verdict.ACCEPTED)

    def test_all_31_representative_mutants_are_rejected(self) -> None:
        for record in records():
            fixture = self.root / "examples" / str(record["problem_id"])
            with self.subTest(problem=record["problem_id"]):
                result = self.judge.judge(
                    fixture / "wrong_off_by_one.py", fixture / "problem.json",
                    fixture / "hidden_tests.json", phase="hidden")
                self.assertIs(result.verdict, Verdict.WRONG_ANSWER)


if __name__ == "__main__":
    unittest.main()
