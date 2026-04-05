import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesRubyTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("ruby", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_rubocop_offenses(self):
        f, result = self._run("rubocop_offenses")
        self.assertEqual(result.filter_name, "rubocop")
        self.assertIn("rubocop:", result.output)
        self.assertIn("offenses", result.output)

    def test_rspec_failures(self):
        f, result = self._run("rspec_failures")
        self.assertEqual(result.filter_name, "rspec")
        self.assertIn("RSpec: 2 examples, 1 failure", result.output)
        self.assertIn("User saves to database", result.output)
        self.assertIn("expected: true", result.output)
