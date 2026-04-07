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
        self.assertIn("rubocop: 20 offenses in 6 files", result.output)
        self.assertIn("app/controllers/api.rb (5)", result.output)
        self.assertIn("Gemfile (4)", result.output)
        self.assertIn("app/models/post.rb (2)", result.output)
        self.assertIn("Style/Documentation", result.output)
        self.assertIn("Lint/Syntax", result.output)

    def test_rspec_failures(self):
        f, result = self._run("rspec_failures")
        self.assertEqual(result.filter_name, "rspec")
        self.assertIn("RSpec: 4 examples, 1 failure", result.output)
        self.assertIn("Account builds the expected email address", result.output)
        self.assertIn("./spec/models/account_spec.rb:16", result.output)
        self.assertIn('expected: "ada@exmple.com"', result.output)
