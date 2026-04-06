import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersTestsTests(unittest.TestCase):
    def test_playwright_json_summary_keeps_failure_details(self):
        stdout = """{
  "stats": {
    "expected": 2,
    "unexpected": 1,
    "skipped": 0,
    "duration": 1500.5
  },
  "suites": [
    {
      "title": "auth.spec.ts",
      "specs": [
        {
          "title": "logs in",
          "ok": false,
          "tests": [
            {
              "status": "unexpected",
              "results": [
                {
                  "status": "failed",
                  "errors": [
                    {
                      "message": "Error: expect(locator).toHaveText(expected)\\nExpected: Submit\\nReceived: Loading"
                    }
                  ]
                }
              ]
            }
          ]
        }
      ],
      "suites": []
    }
  ]
}"""
        result = filter_output(
            "pytk-ai playwright test",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai playwright test"),
        )
        self.assertEqual(result.filter_name, "playwright")
        self.assertIn("PASS (2) FAIL (1)", result.output)
        self.assertIn("1. logs in", result.output)
        self.assertIn("Expected: Submit", result.output)
        self.assertIn("Time: 1500ms", result.output)

    def test_playwright_text_fallback_uses_summary_counts(self):
        stdout = """✗ should render dashboard
  Error: page.goto: net::ERR_CONNECTION_REFUSED

1 failed
3 passed (7.3s)
"""
        result = filter_output(
            "pytk-ai playwright test",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai playwright test"),
        )
        self.assertEqual(result.filter_name, "playwright")
        self.assertIn("PASS (3) FAIL (1)", result.output)
        self.assertIn("should render dashboard", result.output)
        self.assertIn("ERR_CONNECTION_REFUSED", result.output)

    def test_vitest_json_summary_handles_prefixed_output(self):
        stdout = """Scope: all 6 workspace projects

{"numTotalTests": 5, "numPassedTests": 4, "numFailedTests": 1, "numPendingTests": 0, "testResults": [{"name": "src/auth.test.ts", "assertionResults": [{"fullName": "auth logs in", "status": "failed", "failureMessages": ["AssertionError: expected true to be false"]}]}], "startTime": 1000, "endTime": 1450}
"""
        result = filter_output(
            "pytk-ai vitest run",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai vitest run"),
        )
        self.assertEqual(result.filter_name, "vitest")
        self.assertIn("PASS (4) FAIL (1)", result.output)
        self.assertIn("auth logs in", result.output)
        self.assertIn("AssertionError", result.output)
        self.assertIn("Time: 450ms", result.output)

    def test_vitest_text_fallback_uses_failure_blocks(self):
        stdout = """
FAIL  src/auth.test.ts
  [x] auth logs in
    AssertionError: expected true to be false

 Tests  1 failed | 3 passed
 Duration  520ms
"""
        result = filter_output(
            "pytk-ai vitest run",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai vitest run"),
        )
        self.assertEqual(result.filter_name, "vitest")
        self.assertIn("PASS (3) FAIL (1)", result.output)
        self.assertIn("FAIL  src/auth.test.ts", result.output)
        self.assertIn("AssertionError", result.output)

    def test_cargo_test_aggregates_multiple_suite_summaries(self):
        stdout = """running 2 tests
test alpha ... ok
test beta ... ok
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

running 3 tests
test gamma ... ok
test delta ... ok
test epsilon ... ok
test result: ok. 3 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
"""
        result = filter_output(
            "cargo test --workspace",
            stdout,
            "",
            0,
            plan=plan_command("cargo test --workspace"),
        )
        self.assertEqual(result.filter_name, "test.cargo")
        self.assertEqual(
            result.output,
            "cargo test: ok (2 suites, 5 passed; 0 failed; 1 ignored)",
        )

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

    def test_wrapped_pytest_command_reuses_pytest_reducer(self):
        stdout = """============================= test session starts ==============================
collected 2 items

=================================== FAILURES ===================================
__________________________ test_addition __________________________

    def test_addition():
>       assert 1 == 2
E       assert 1 == 2

tests/test_demo.py:4: AssertionError
=========================== short test summary info ============================
FAILED tests/test_demo.py::test_addition - assert 1 == 2
========================= 1 failed, 1 passed in 0.12s ==========================
"""
        result = filter_output(
            "pytk-ai test pytest -q",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai test pytest -q"),
        )
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest:", result.output)
        self.assertIn("tests/test_demo.py::test_addition", result.output)

    def test_wrapped_go_test_command_reuses_go_reducer(self):
        stdout = """=== RUN   TestThing
--- FAIL: TestThing (0.00s)
    thing_test.go:12: expected 2, got 1
FAIL	github.com/acme/demo	0.005s
"""
        result = filter_output(
            "pytk-ai test go test ./...",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai test go test ./..."),
        )
        self.assertEqual(result.filter_name, "go.test")
        self.assertIn("Go test:", result.output)
        self.assertIn("TestThing", result.output)

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

    def test_cargo_test_compile_errors_use_build_style_summary(self):
        stderr = """Compiling demo v0.1.0 (/tmp/demo)
error[E0425]: cannot find value `missing` in this scope
 --> src/main.rs:2:5
  |
2 |     missing();
  |     ^^^^^^^ not found in this scope
"""
        result = filter_output(
            "cargo test",
            "",
            stderr,
            101,
            plan=plan_command("cargo test"),
        )
        self.assertEqual(result.filter_name, "test.cargo")
        self.assertIn("cargo test: 1 errors, 0 warnings", result.output)
        self.assertIn("src/main.rs", result.output)
        self.assertIn("E0425", result.output)
