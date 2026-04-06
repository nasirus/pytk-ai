import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersDotnetTests(unittest.TestCase):
    def test_dotnet_build_groups_errors_and_warnings(self):
        stderr = """src/Program.cs(42,15): error CS0103: The name 'foo' does not exist in the current context
src/Program.cs(25,10): warning CS0219: The variable 'x' is assigned but its value is never used

Build FAILED.
    1 Warning(s)
    1 Error(s)

Time Elapsed 00:00:04.20
"""
        result = filter_output(
            "dotnet build src/App.csproj",
            "",
            stderr,
            1,
            plan=plan_command("dotnet build src/App.csproj"),
        )
        self.assertEqual(result.filter_name, "dotnet.build")
        self.assertIn("fail dotnet build", result.output)
        self.assertIn("error CS0103", result.output)
        self.assertIn("warning CS0219", result.output)

    def test_dotnet_test_summarizes_failed_tests(self):
        stdout = """Failed Example.Tests.AuthTests.Login_fails_for_invalid_token [42 ms]
  Assert.Equal() Failure: Expected 401 Actual 200

Failed!  - Failed: 1, Passed: 9, Skipped: 2, Total: 12, Duration: 187 ms - Example.Tests.dll (net8.0)
Time Elapsed 00:00:02.00
"""
        result = filter_output(
            "dotnet test tests/Example.Tests.csproj",
            stdout,
            "",
            1,
            plan=plan_command("dotnet test tests/Example.Tests.csproj"),
        )
        self.assertEqual(result.filter_name, "dotnet.test")
        self.assertIn("1 failed", result.output)
        self.assertIn("Login_fails_for_invalid_token", result.output)
        self.assertIn("Assert.Equal() Failure", result.output)

    def test_dotnet_restore_summarizes_success(self):
        stdout = """Determining projects to restore...
  Restored /repo/src/App/App.csproj (in 153 ms).
  Restored /repo/tests/App.Tests/App.Tests.csproj (in 167 ms).

Build succeeded.
    0 Warning(s)
    0 Error(s)

Time Elapsed 00:00:01.10
"""
        result = filter_output(
            "dotnet restore",
            stdout,
            "",
            0,
            plan=plan_command("dotnet restore"),
        )
        self.assertEqual(result.filter_name, "dotnet.restore")
        self.assertEqual(
            result.output,
            "ok dotnet restore: 2 restored, 0 errors, 0 warnings (00:00:01.10)",
        )

    def test_dotnet_format_check_lists_files_needing_formatting(self):
        stderr = """/repo/src/Behavior.cs(13,32): error IDE0055: Fix formatting
/repo/src/Api.cs(21,8): error IDE0055: Fix formatting
"""
        result = filter_output(
            "dotnet format --verify-no-changes",
            "",
            stderr,
            2,
            plan=plan_command("dotnet format --verify-no-changes"),
        )
        self.assertEqual(result.filter_name, "dotnet.format")
        self.assertIn("Format: 2 files need formatting", result.output)
        self.assertIn("Behavior.cs", result.output)
        self.assertIn("Run `dotnet format` to apply fixes", result.output)

    def test_dotnet_format_write_lists_changed_files(self):
        stdout = """Formatted code file '/repo/src/Behavior.cs'.
Formatted code file '/repo/src/Api.cs'.
"""
        result = filter_output(
            "dotnet format --write",
            stdout,
            "",
            0,
            plan=plan_command("dotnet format --write"),
        )
        self.assertEqual(result.filter_name, "dotnet.format")
        self.assertIn("ok dotnet format: formatted 2 files", result.output)
        self.assertIn("src/Behavior.cs", result.output)
