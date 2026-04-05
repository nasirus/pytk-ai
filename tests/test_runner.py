import sys
import unittest

from ptk.runner import run_command


class RunnerTests(unittest.TestCase):
    def test_run_command_returns_filtered_success_result(self):
        result = run_command(f'{sys.executable} -c "print(123)"')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filtered_output, "123")
        self.assertEqual(result.executed_command, f'{sys.executable} -c "print(123)"')

    def test_run_command_preserves_non_zero_exit_and_stderr(self):
        result = run_command(
            f"{sys.executable} -c \"import sys; sys.stderr.write('bad\\n'); sys.exit(3)\""
        )
        self.assertEqual(result.exit_code, 3)
        self.assertIn("bad", result.filtered_output)

    def test_run_command_reports_timeout_without_raising(self):
        result = run_command(
            f'{sys.executable} -c "import time; time.sleep(1)"',
            timeout=0.01,
        )
        self.assertEqual(result.exit_code, 124)
        self.assertIn("timeout", result.error)

    def test_run_command_accepts_env_overrides(self):
        result = run_command(
            f"{sys.executable} -c \"import os; print(os.environ['PTK_TEST_VALUE'])\"",
            env={"PTK_TEST_VALUE": "set"},
        )
        self.assertEqual(result.filtered_output, "set")

    def test_run_command_returns_structured_error_for_empty_input(self):
        result = run_command("   ")
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error, "empty-command")
