import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersTestsTests(unittest.TestCase):
    def test_generic_test_wrapper_is_failure_focused(self):
        stdout = """PASS src/a.test.ts
FAIL src/b.test.ts
  should fail loudly

Test Suites: 1 failed, 1 passed, 2 total
Tests:       1 failed, 3 passed, 4 total
"""
        result = filter_output(
            "npm test",
            stdout,
            "",
            1,
            plan=plan_command("npm test"),
        )
        self.assertEqual(result.filter_name, "test.generic")
        self.assertIn("FAIL src/b.test.ts", result.output)
        self.assertIn("Test Suites:", result.output)

    def test_cargo_test_keeps_failures_and_summary(self):
        stdout = """running 2 tests
test ok_case ... ok
test failing_case ... FAILED

failures:

    failing_case

test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
"""
        result = filter_output(
            "cargo test",
            stdout,
            "",
            101,
            plan=plan_command("cargo test"),
        )
        self.assertEqual(result.filter_name, "test.cargo")
        self.assertIn("failures:", result.output)
        self.assertIn("failing_case", result.output)
        self.assertIn("test result:", result.output)
