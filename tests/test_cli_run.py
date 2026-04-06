import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from pytk_ai.cli import main
from pytk_ai.models import CommandResult


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

    @patch("pytk_ai.cli.run_test_command")
    def test_main_test_executes_wrapper_surface(self, run_test_command):
        run_test_command.return_value = CommandResult(
            original_command="pytest -q",
            executed_command="pytest -q",
            planned_command="pytk-ai test 'pytest -q'",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Pytest: 1 passed",
            exit_code=0,
            filter_name="python.pytest",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["test", "pytest", "-q"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "Pytest: 1 passed\n")
        run_test_command.assert_called_once_with("pytest -q", max_output_lines=200)

    @patch("pytk_ai.cli.run_format_command")
    def test_main_format_executes_wrapper_surface(self, run_format_command):
        run_format_command.return_value = CommandResult(
            original_command="prettier --check .",
            executed_command="npx prettier --check .",
            planned_command="pytk-ai format prettier --check .",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Format (prettier): 1 files need formatting",
            exit_code=1,
            filter_name="format.prettier",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["format", "prettier", "--check", "."])

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            buffer.getvalue(), "Format (prettier): 1 files need formatting\n"
        )
        run_format_command.assert_called_once_with(
            "prettier --check .", max_output_lines=200
        )

    @patch("pytk_ai.cli.run_dotnet_command")
    def test_main_dotnet_executes_wrapper_surface(self, run_dotnet_command):
        run_dotnet_command.return_value = CommandResult(
            original_command="build src/App.csproj",
            executed_command="dotnet build src/App.csproj",
            planned_command="pytk-ai dotnet build src/App.csproj",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="ok dotnet build: 1 projects, 0 errors, 0 warnings (00:00:01.24)",
            exit_code=0,
            filter_name="dotnet.build",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["dotnet", "build", "src/App.csproj"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            buffer.getvalue(),
            "ok dotnet build: 1 projects, 0 errors, 0 warnings (00:00:01.24)\n",
        )
        run_dotnet_command.assert_called_once_with(
            "build src/App.csproj", max_output_lines=200
        )

    @patch("pytk_ai.cli.run_gt_command")
    def test_main_gt_executes_wrapper_surface(self, run_gt_command):
        run_gt_command.return_value = CommandResult(
            original_command="submit",
            executed_command="gt submit",
            planned_command="pytk-ai gt submit",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="pushed feat/add-auth\ncreated PR #42 feat/add-auth",
            exit_code=0,
            filter_name="gt.submit",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["gt", "submit"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            buffer.getvalue(), "pushed feat/add-auth\ncreated PR #42 feat/add-auth\n"
        )
        run_gt_command.assert_called_once_with("submit", max_output_lines=200)

    @patch("pytk_ai.cli.run_json_command")
    def test_main_json_executes_wrapper_surface(self, run_json_command):
        run_json_command.return_value = CommandResult(
            original_command="data.json",
            executed_command="data.json",
            planned_command="pytk-ai json data.json",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="{\n  name: string\n}",
            exit_code=0,
            filter_name="json.schema",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["json", "data.json", "--schema"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "{\n  name: string\n}\n")
        run_json_command.assert_called_once_with(
            "data.json", schema_only=True, max_depth=3
        )

    @patch("pytk_ai.cli.run_log_command")
    def test_main_log_executes_wrapper_surface(self, run_log_command):
        run_log_command.return_value = CommandResult(
            original_command="app.log",
            executed_command="app.log",
            planned_command="pytk-ai log app.log",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Log Summary",
            exit_code=0,
            filter_name="log",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["log", "app.log"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "Log Summary\n")

    @patch("pytk_ai.cli.run_env_command")
    def test_main_env_executes_wrapper_surface(self, run_env_command):
        run_env_command.return_value = CommandResult(
            original_command="AWS",
            executed_command="env",
            planned_command="pytk-ai env AWS",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Cloud/Services:",
            exit_code=0,
            filter_name="env",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["env", "AWS"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "Cloud/Services:\n")
        run_env_command.assert_called_once_with("AWS", show_all=False)

    @patch("pytk_ai.cli.run_deps_command")
    def test_main_deps_executes_wrapper_surface(self, run_deps_command):
        run_deps_command.return_value = CommandResult(
            original_command=".",
            executed_command=".",
            planned_command="pytk-ai deps .",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Rust (Cargo.toml):",
            exit_code=0,
            filter_name="deps",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["deps"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "Rust (Cargo.toml):\n")
        run_deps_command.assert_called_once_with(".")

    @patch("pytk_ai.cli.run_summary_command")
    def test_main_summary_executes_wrapper_surface(self, run_summary_command):
        run_summary_command.return_value = CommandResult(
            original_command="pytest -q",
            executed_command="pytest -q",
            planned_command="pytk-ai summary 'pytest -q'",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="[FAIL] Command: pytest -q",
            exit_code=1,
            filter_name="summary",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["summary", "pytest", "-q"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(buffer.getvalue(), "[FAIL] Command: pytest -q\n")
        run_summary_command.assert_called_once_with("pytest -q")

    @patch("pytk_ai.cli.run_smart_command")
    def test_main_smart_executes_wrapper_surface(self, run_smart_command):
        run_smart_command.return_value = CommandResult(
            original_command="main.py",
            executed_command="main.py",
            planned_command="pytk-ai smart main.py",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="Python module (1 fn) - 3 lines\nuses: json",
            exit_code=0,
            filter_name="smart",
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["smart", "main.py"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            buffer.getvalue(), "Python module (1 fn) - 3 lines\nuses: json\n"
        )
        run_smart_command.assert_called_once_with("main.py")

    @patch("pytk_ai.cli.run_err_command")
    def test_main_err_executes_wrapper_surface(self, run_err_command):
        run_err_command.return_value = CommandResult(
            original_command="python -m pytest -q",
            executed_command="python -m pytest -q",
            planned_command="pytk-ai err 'python -m pytest -q'",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="RuntimeError: boom",
            exit_code=1,
            filter_name="err",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["err", "python", "-m", "pytest", "-q"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(buffer.getvalue(), "RuntimeError: boom\n")
        run_err_command.assert_called_once_with(
            "python -m pytest -q", max_output_lines=200
        )

    @patch("pytk_ai.cli.run_psql_command")
    def test_main_psql_executes_wrapper_surface(self, run_psql_command):
        run_psql_command.return_value = CommandResult(
            original_command="-c 'select 1'",
            executed_command="psql -c 'select 1'",
            planned_command="pytk-ai psql -c 'select 1'",
            managed=True,
            changed=True,
            stdout="",
            stderr="",
            filtered_output="?column?\n1",
            exit_code=0,
            filter_name="psql",
        )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = main(["psql", "-c", "select 1"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "?column?\n1\n")
        run_psql_command.assert_called_once_with("-c 'select 1'", max_output_lines=200)

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
