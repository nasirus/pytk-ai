import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersGoTests(unittest.TestCase):
    def test_go_test_summarizes_failed_package_and_test(self):
        stdout = """ok  example.com/project/pkg/a 0.015s
--- FAIL: TestThing (0.00s)
    thing_test.go:12: expected 2, got 1
FAIL
FAIL    example.com/project/pkg/b  0.023s
"""
        result = filter_output(
            "go test ./...",
            stdout,
            "",
            1,
            plan=plan_command("go test ./..."),
        )
        self.assertEqual(result.filter_name, "go.test")
        self.assertIn("Go test: 1 packages passed, 1 packages failed", result.output)
        self.assertIn("[FAIL] TestThing", result.output)
        self.assertIn("expected 2, got 1", result.output)

    def test_non_test_build_vet_go_commands_keep_generic_output(self):
        result = filter_output(
            "go version",
            "go version go1.24.1 linux/amd64\n",
            "",
            0,
            plan=plan_command("go version"),
        )
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("go version go1.24.1 linux/amd64", result.output)

    def test_golangci_lint_groups_by_linter(self):
        stderr = """pkg/server/server.go:12:2: Error return value of `w.Write` is not checked (errcheck)
pkg/server/server.go:20:6: exported type Foo should have comment or be unexported [revive]
"""
        result = filter_output(
            "golangci-lint run",
            "",
            stderr,
            1,
            plan=plan_command("golangci-lint run"),
        )
        self.assertEqual(result.filter_name, "golangci-lint")
        self.assertIn("golangci-lint: 2 issues in 1 files", result.output)
        self.assertIn("errcheck", result.output)
        self.assertIn("revive", result.output)

    def test_golangci_lint_json_summary_prefers_structured_output(self):
        stdout = """{
  "Issues": [
    {
      "FromLinter": "errcheck",
      "Text": "Error return value not checked",
      "SourceLines": ["    if err := foo(); err != nil {"],
      "Pos": {"Filename": "pkg/server/server.go", "Line": 12, "Column": 2, "Offset": 120}
    },
    {
      "FromLinter": "revive",
      "Text": "exported type Foo should have comment",
      "SourceLines": ["type Foo struct {}"],
      "Pos": {"Filename": "pkg/server/server.go", "Line": 20, "Column": 6, "Offset": 220}
    }
  ]
}
"""
        result = filter_output(
            "golangci-lint run",
            stdout,
            "",
            1,
            plan=plan_command("golangci-lint run"),
        )
        self.assertEqual(result.filter_name, "golangci-lint")
        self.assertIn("golangci-lint: 2 issues in 1 files", result.output)
        self.assertIn("Top linters: errcheck (1x), revive (1x)", result.output)
        self.assertIn("pkg/server/server.go (2 issues)", result.output)
        self.assertIn("-> if err := foo(); err != nil {", result.output)
