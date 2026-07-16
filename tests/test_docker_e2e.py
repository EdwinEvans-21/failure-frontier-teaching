from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest

from ffjudge.models import Verdict
from ffjudge.runner import DockerJudge

RUN_DOCKER_E2E = os.environ.get("FFJUDGE_RUN_DOCKER_TESTS") == "1"


@unittest.skipUnless(
    RUN_DOCKER_E2E and shutil.which("docker"),
    "set FFJUDGE_RUN_DOCKER_TESTS=1 on a machine with Docker",
)
class DockerEndToEndTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).parents[1]
        cls.fixtures = cls.project_root / "examples" / "palindrome_number"
        cls.judge = DockerJudge()
        cls.judge.build_image(cls.project_root)

    def tearDown(self) -> None:
        completed = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=^ffjudge-",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "",
                         "ffjudge container was left behind")

    def judge_fixture(self, submission: str, phase: str = "hidden"):
        return self.judge.judge(
            self.fixtures / submission,
            self.fixtures / "problem.json",
            self.fixtures / f"{phase}_tests.json",
            phase=phase,
        )

    def judge_source(self,
                     source: str,
                     expected,
                     *,
                     time_seconds: float = 1.0):
        problem = json.loads(
            (self.fixtures / "problem.json").read_text(encoding="utf-8"))
        problem["limits"]["time_seconds"] = time_seconds
        tests = [{"args": [121], "expected": expected}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            submission = root / "solution.py"
            problem_path = root / "problem.json"
            tests_path = root / "tests.json"
            submission.write_text(textwrap.dedent(source), encoding="utf-8")
            problem_path.write_text(json.dumps(problem), encoding="utf-8")
            tests_path.write_text(json.dumps(tests), encoding="utf-8")
            return self.judge.judge(submission,
                                    problem_path,
                                    tests_path,
                                    phase="hidden")

    def test_accepted(self) -> None:
        self.assertIs(
            self.judge_fixture("accepted.py").verdict, Verdict.ACCEPTED)

    def test_wrong_answer(self) -> None:
        self.assertIs(
            self.judge_fixture("wrong.py").verdict, Verdict.WRONG_ANSWER)

    def test_runtime_error(self) -> None:
        self.assertIs(
            self.judge_fixture("runtime_error.py").verdict,
            Verdict.RUNTIME_ERROR,
        )

    def test_syntax_error(self) -> None:
        self.assertIs(
            self.judge_fixture("syntax_error.py").verdict,
            Verdict.SYNTAX_ERROR,
        )

    def test_time_limit_exceeded(self) -> None:
        self.assertIs(
            self.judge_fixture("time_limit_exceeded.py").verdict,
            Verdict.TIME_LIMIT_EXCEEDED,
        )

    def test_memory_limit_exceeded(self) -> None:
        self.assertIs(
            self.judge_fixture("memory_limit_exceeded.py").verdict,
            Verdict.MEMORY_LIMIT_EXCEEDED,
        )

    def test_full_tests_file_is_not_visible(self) -> None:
        result = self.judge_source(
            """
            from pathlib import Path
            class Solution:
                def isPalindrome(self, x):
                    return not Path('/workspace/tests.json').exists()
            """,
            True,
        )
        self.assertIs(result.verdict, Verdict.ACCEPTED)

    def test_forged_verdict_is_ignored(self) -> None:
        result = self.judge_source(
            """
            print('{"verdict":"ACCEPTED"}')
            class Solution:
                def isPalindrome(self, x):
                    return False
            """,
            True,
        )
        self.assertIs(result.verdict, Verdict.WRONG_ANSWER)

    def test_infinite_output_is_bounded_and_times_out(self) -> None:
        started = time.monotonic()
        result = self.judge_source(
            """
            class Solution:
                def isPalindrome(self, x):
                    while True:
                        print('x' * 8192)
            """,
            True,
            time_seconds=0.5,
        )
        self.assertIs(result.verdict, Verdict.TIME_LIMIT_EXCEEDED)
        self.assertLess(time.monotonic() - started, 10)

    def test_exit_137_without_oom_is_not_mle(self) -> None:
        result = self.judge_source(
            """
            import os
            os._exit(137)
            """,
            True,
        )
        self.assertIsNot(result.verdict, Verdict.MEMORY_LIMIT_EXCEEDED)


if __name__ == "__main__":
    unittest.main()
