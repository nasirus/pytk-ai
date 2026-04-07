import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesGenericTests(unittest.TestCase):
    def _run(self, name):
        fixture = load_fixture("generic", name)
        result = filter_output(
            fixture["command"],
            fixture["stdout"],
            fixture["stderr"],
            fixture["exit_code"],
            plan=plan_command(fixture["command"]),
        )
        return fixture, result

    def test_ansi_output(self):
        fixture, result = self._run("ansi_output")
        self.assertEqual(result.filter_name, "generic")
        self.assertNotIn("\x1b", result.output)
        self.assertIn("ERROR build failed", result.output)
        self.assertIn("PASS 3 tests", result.output)

    def test_git_status_hints(self):
        fixture, result = self._run("git_status_hints")
        self.assertEqual(result.filter_name, "git.status")
        self.assertIn('(use "git pull"', fixture["stdout"])
        self.assertNotIn('(use "git pull"', result.output)
        self.assertNotIn('(use "git add <file>..."', result.output)
        self.assertIn("docs/report.md", result.output)
        self.assertIn("README.md", result.output)
        self.assertIn("tmp.log", result.output)
