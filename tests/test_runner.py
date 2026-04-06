import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pytk_ai.models import ExecutionResult
from pytk_ai.runner import (
    run_command,
    run_deps_command,
    run_dotnet_command,
    run_env_command,
    run_err_command,
    run_format_command,
    run_gt_command,
    run_json_command,
    run_log_command,
    run_psql_command,
    run_smart_command,
    run_summary_command,
    run_test_command,
)


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
            f"{sys.executable} -c \"import os; print(os.environ['PYTK_AI_TEST_VALUE'])\"",
            env={"PYTK_AI_TEST_VALUE": "set"},
        )
        self.assertEqual(result.filtered_output, "set")

    def test_run_command_returns_structured_error_for_empty_input(self):
        result = run_command("   ")
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error, "empty-command")

    @patch("pytk_ai.runner.execute_raw")
    def test_run_test_command_reuses_specialized_test_filter(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="pytest -q",
            stdout=(
                "============================= test session starts ==============================\n"
                "=================================== FAILURES ===================================\n"
                "__________________________ test_addition __________________________\n"
                "FAILED tests/test_demo.py::test_addition - assert 1 == 2\n"
                "========================= 1 failed, 1 passed in 0.12s ==========================\n"
            ),
            stderr="",
            exit_code=1,
        )

        result = run_test_command("pytest -q")

        self.assertEqual(result.executed_command, "pytest -q")
        self.assertEqual(result.planned_command, "pytk-ai test 'pytest -q'")
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest:", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_test_command_keeps_generic_failures_only_summary(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="npm test",
            stdout=(
                "PASS src/a.test.ts\n"
                "FAIL src/b.test.ts\n"
                "Test Suites: 1 failed, 1 passed, 2 total\n"
                "Tests:       1 failed, 3 passed, 4 total\n"
            ),
            stderr="",
            exit_code=1,
        )

        result = run_test_command("npm test")

        self.assertEqual(result.filter_name, "test.generic")
        self.assertIn("FAIL src/b.test.ts", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_err_command_keeps_errors_only_summary(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="python -m pytest -q",
            stdout="collected 2 items\n",
            stderr=(
                "warning: deprecated config\n"
                "Traceback (most recent call last):\n"
                '  File "demo.py", line 3, in <module>\n'
                "    raise RuntimeError('boom')\n"
                "RuntimeError: boom\n"
            ),
            exit_code=1,
        )

        result = run_err_command("python -m pytest -q")

        self.assertEqual(result.executed_command, "python -m pytest -q")
        self.assertEqual(result.planned_command, "pytk-ai err 'python -m pytest -q'")
        self.assertEqual(result.filter_name, "err")
        self.assertIn("warning: deprecated config", result.filtered_output)
        self.assertIn("Traceback", result.filtered_output)
        self.assertNotIn("collected 2 items", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_psql_command_reuses_psql_filter(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="psql -c 'select * from users'",
            stdout=(" id | username\n----+----------\n  1 | alice\n(1 row)\n"),
            stderr="",
            exit_code=0,
        )

        result = run_psql_command("-c 'select * from users'")

        self.assertEqual(result.executed_command, "psql -c 'select * from users'")
        self.assertEqual(
            result.planned_command, "pytk-ai psql -c 'select * from users'"
        )
        self.assertEqual(result.filter_name, "psql")
        self.assertEqual(result.filtered_output, "id\tusername\n1\talice")

    @patch("pytk_ai.runner.execute_raw")
    def test_run_format_command_reuses_specialized_formatter_filter(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="npx prettier --check .",
            stdout="",
            stderr=(
                "Checking formatting...\n"
                "[warn] src/app.ts\n"
                "[warn] Code style issues found in 1 file. Run Prettier with --write to fix.\n"
            ),
            exit_code=1,
        )

        result = run_format_command("prettier --check .")

        self.assertEqual(result.executed_command, "npx prettier --check .")
        self.assertEqual(result.planned_command, "pytk-ai format prettier --check .")
        self.assertEqual(result.filter_name, "format.prettier")
        self.assertIn(
            "Format (prettier): 1 files need formatting", result.filtered_output
        )

    @patch("pytk_ai.runner.execute_raw")
    @patch("pytk_ai.runner.os.getcwd", return_value="/workspace")
    @patch("pytk_ai.runner.Path.read_text")
    def test_run_format_command_auto_detects_ruff_from_pyproject(
        self,
        read_text,
        getcwd,
        execute_raw,
    ):
        del getcwd
        read_text.return_value = '[tool.ruff.format]\nquote-style = "double"\n'
        execute_raw.return_value = ExecutionResult(
            command="ruff format --check .",
            stdout="2 files left unchanged\n",
            stderr="",
            exit_code=0,
        )

        with patch(
            "pytk_ai.runner.Path.exists",
            autospec=True,
            side_effect=lambda path_obj: str(path_obj).endswith("pyproject.toml"),
        ):
            result = run_format_command("--check .")

        self.assertEqual(result.executed_command, "ruff format --check .")
        self.assertEqual(result.planned_command, "pytk-ai format --check .")
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("all files formatted", result.filtered_output.lower())

    @patch("pytk_ai.runner.execute_raw")
    def test_run_dotnet_command_reuses_dotnet_filter(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="dotnet build src/App.csproj",
            stdout="Build succeeded.\n    0 Warning(s)\n    0 Error(s)\n\nTime Elapsed 00:00:01.24\n",
            stderr="",
            exit_code=0,
        )

        result = run_dotnet_command("build src/App.csproj")

        self.assertEqual(result.executed_command, "dotnet build src/App.csproj")
        self.assertEqual(result.planned_command, "pytk-ai dotnet build src/App.csproj")
        self.assertEqual(result.filter_name, "dotnet.build")
        self.assertIn("ok dotnet build", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_gt_command_reuses_graphite_filter(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="gt submit",
            stdout="Pushed branch feat/add-auth\nCreated pull request #42 for feat/add-auth\n",
            stderr="",
            exit_code=0,
        )

        result = run_gt_command("submit")

        self.assertEqual(result.executed_command, "gt submit")
        self.assertEqual(result.planned_command, "pytk-ai gt submit")
        self.assertEqual(result.filter_name, "gt.submit")
        self.assertIn("created PR #42", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_gt_command_remaps_git_like_subcommands(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="git status",
            stdout="## main\n",
            stderr="",
            exit_code=0,
        )

        result = run_gt_command("status")

        self.assertEqual(result.executed_command, "git status")
        self.assertEqual(result.planned_command, "pytk-ai gt status")
        self.assertEqual(result.filter_name, "git.status")

    def test_run_json_command_renders_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.json"
            path.write_text('{"name":"demo","count":1}', encoding="utf-8")
            result = run_json_command(str(path), schema_only=True)
        self.assertEqual(result.filter_name, "json.schema")
        self.assertIn("name: string", result.filtered_output)

    def test_run_log_command_renders_deduplicated_summary(self):
        result = run_log_command(
            "2024-01-01 10:00:00 ERROR: fail /srv/api\n"
            "2024-01-01 10:00:01 ERROR: fail /srv/api\n"
        )
        self.assertEqual(result.filter_name, "log")
        self.assertIn("1 unique", result.filtered_output)

    def test_run_env_command_masks_sensitive_values(self):
        result = run_env_command(
            "API", env={"API_TOKEN": "secret-token", "HOME": "/home/demo"}
        )
        self.assertEqual(result.filter_name, "env")
        self.assertIn("API_TOKEN=se****en", result.filtered_output)

    def test_run_deps_command_summarizes_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "requirements.txt").write_text(
                "requests==2.0.0\n", encoding="utf-8"
            )
            result = run_deps_command(str(root))
        self.assertEqual(result.filter_name, "deps")
        self.assertIn("Python (requirements.txt):", result.filtered_output)

    @patch("pytk_ai.runner.execute_raw")
    def test_run_summary_command_summarizes_arbitrary_output(self, execute_raw):
        execute_raw.return_value = ExecutionResult(
            command="pytest -q",
            stdout="1 passed, 2 failed in 0.2s\nFAILED demo::test_a\n",
            stderr="",
            exit_code=1,
        )
        result = run_summary_command("pytest -q")
        self.assertEqual(result.filter_name, "summary")
        self.assertIn("Test Results:", result.filtered_output)

    def test_run_smart_command_summarizes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "main.py"
            path.write_text(
                "import json\n\ndef load_config():\n    return {}\n",
                encoding="utf-8",
            )
            result = run_smart_command(str(path))
        self.assertEqual(result.filter_name, "smart")
        self.assertEqual(len(result.filtered_output.splitlines()), 2)
