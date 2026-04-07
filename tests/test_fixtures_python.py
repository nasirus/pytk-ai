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
        self.assertIn("Ruff: 5 issues in 4 files (4 fixable)", result.output)
        self.assertIn("F401 (4x)", result.output)
        self.assertIn("F841 (1x)", result.output)
        self.assertIn("src/app.py (2 issues): F401 (2)", result.output)
        self.assertIn("src/lib/util.py (1 issues): F841 (1)", result.output)

    def test_mypy_errors(self):
        f, result = self._run("mypy_errors")
        self.assertEqual(result.filter_name, "python.mypy")
        self.assertIn('src/pkg/core.py:5: note: Revealed type is "int"', result.output)
        self.assertIn("mypy: 6 errors in 4 files", result.output)
        self.assertIn(
            "Top codes: return-value (3x), arg-type (2x), name-defined (1x)",
            result.output,
        )
        self.assertIn("src/app.py (2)", result.output)
        self.assertIn("src/models/user.py (2)", result.output)
        self.assertIn("src/utils.py (1)", result.output)

    def test_pytest_failures(self):
        f, result = self._run("pytest_failures")
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest: 2 failed, 3 passed in 0.01s", result.output)
        self.assertIn("[FAIL] test_divide_fail", result.output)
        self.assertIn("assert 2.5 == 3", result.output)
        self.assertIn("[FAIL] test_contains", result.output)
        self.assertIn("AssertionError: assert 'pytest' in 'python'", result.output)
