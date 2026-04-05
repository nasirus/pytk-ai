import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesPythonTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("python", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_ruff_check(self):
        f, result = self._run("ruff_check")
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("Ruff: 3 issues in 2 files", result.output)
        self.assertIn("F401 (2x)", result.output)

    def test_mypy_errors(self):
        f, result = self._run("mypy_errors")
        self.assertEqual(result.filter_name, "python.mypy")
        self.assertIn("mypy:", result.output)
        self.assertIn("errors", result.output)

    def test_pytest_failures(self):
        f, result = self._run("pytest_failures")
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest:", result.output)
        self.assertIn("[FAIL] test_failure", result.output)
        self.assertIn("assert 1 == 2", result.output)
