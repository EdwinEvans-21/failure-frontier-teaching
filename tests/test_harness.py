from pathlib import Path
from typing import Any
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


class HarnessProtocolTests(unittest.TestCase):

    def run_submission(self,
                       source: str,
                       *,
                       timeout: float = 3) -> tuple[int, str]:
        project_root = Path(__file__).parents[1]
        problem = json.loads((project_root / "examples" / "palindrome_number" /
                              "problem.json").read_text(encoding="utf-8"))
        request: dict[str, Any] = {
            "entrypoint": problem["entrypoint"],
            "args": [121],
            "kwargs": {},
            "time_seconds": 1.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "solution.py").write_text(textwrap.dedent(source),
                                                   encoding="utf-8")
            (workspace / "case.json").write_text(json.dumps(request),
                                                 encoding="utf-8")
            environment = dict(os.environ, FFJUDGE_WORKSPACE=str(workspace))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "src" / "ffjudge" / "harness.py")
                ],
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
                check=False,
            )
        return completed.returncode, completed.stdout

    @staticmethod
    def result_from(stdout: str) -> dict[str, Any] | None:
        prefix = "FFJUDGE_WORKER_RESULT:"
        for line in reversed(stdout.splitlines()):
            if line.startswith(prefix):
                return json.loads(line[len(prefix):])
        return None

    def test_worker_returns_actual_not_verdict(self) -> None:
        _, stdout = self.run_submission("""
            class Solution:
                def isPalindrome(self, x):
                    return True
            """)
        result = self.result_from(stdout)
        self.assertEqual(result["status"], "ok")
        self.assertIs(result["actual"], True)
        self.assertNotIn("verdict", result)

    def test_runtime_error_is_controlled_and_omits_message(self) -> None:
        _, stdout = self.run_submission("""
            class Solution:
                def isPalindrome(self, x):
                    raise RuntimeError("hidden-data-from-submission")
            """)
        result = self.result_from(stdout)
        self.assertEqual(result["status"], "runtime_error")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertNotIn("hidden-data-from-submission", stdout)

    def test_syntax_error_has_dedicated_status(self) -> None:
        _, stdout = self.run_submission("def broken(:\n    pass\n")
        self.assertEqual(self.result_from(stdout)["status"], "syntax_error")

    def test_fake_accepted_json_is_not_a_worker_result(self) -> None:
        _, stdout = self.run_submission("""
            print('{"verdict":"ACCEPTED"}')
            class Solution:
                def isPalindrome(self, x):
                    return False
            """)
        result = self.result_from(stdout)
        self.assertEqual(result["status"], "ok")
        self.assertIs(result["actual"], False)

    def test_os_exit_zero_produces_no_worker_result(self) -> None:
        returncode, stdout = self.run_submission("""
            import os
            print('{"verdict":"ACCEPTED"}')
            os._exit(0)
            """)
        self.assertEqual(returncode, 0)
        self.assertIsNone(self.result_from(stdout))


if __name__ == "__main__":
    unittest.main()
