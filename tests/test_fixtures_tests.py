import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesTestsTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("tests", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_cargo_test_fail(self):
        f, result = self._run("cargo_test_fail")
        self.assertEqual(result.filter_name, "test.cargo")
        self.assertIn("normalizes_display_email", result.output)
        self.assertIn("rejects_empty_passwords", result.output)
        self.assertIn("uses_uppercase_bonus", result.output)
        self.assertIn("test result: ok. 3 passed; 0 failed", result.output)
        self.assertIn("test result: FAILED. 0 passed; 3 failed", result.output)

    def test_npm_test_fail(self):
        f, result = self._run("npm_test_fail")
        self.assertEqual(result.filter_name, "test.generic")
        self.assertIn("FAIL __tests__/labels.test.js", result.output)
        self.assertIn("Test Suites: 1 failed, 2 passed, 3 total", result.output)
        self.assertIn('Received array: ["alpha", "beta", "gamma"]', f["stderr"])
