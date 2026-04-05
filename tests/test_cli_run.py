import io
import json
import sys
import unittest
from contextlib import redirect_stdout

from pytk_ai.cli import main


class CliRunTests(unittest.TestCase):
    def test_main_run_executes_and_prints_filtered_output(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["run", sys.executable, "-c", "print('ok')"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "ok\n")

    def test_main_run_returns_underlying_exit_code(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(
                [
                    "run",
                    sys.executable,
                    "-c",
                    "import sys; sys.stderr.write('bad\\n'); sys.exit(5)",
                ]
            )
        self.assertEqual(exit_code, 5)
        self.assertIn("bad", buffer.getvalue())

    def test_hook_cursor_emits_updated_input_for_rewritten_command(self):
        stdin = io.StringIO(json.dumps({"tool_input": {"command": "git status"}}))
        stdout = io.StringIO()
        original_stdin = sys.stdin
        try:
            sys.stdin = stdin
            with redirect_stdout(stdout):
                exit_code = main(["hook", "cursor"])
        finally:
            sys.stdin = original_stdin
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {"permission": "allow", "updated_input": {"command": "pytk-ai git status"}},
        )
