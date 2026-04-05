import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersRubyTests(unittest.TestCase):
    def test_rubocop_groups_offenses_by_file(self):
        stdout = """app/models/user.rb:10:5: C: Layout/TrailingWhitespace: Trailing whitespace detected.
app/models/user.rb:12:3: W: Lint/UselessAssignment: Useless assignment to variable - x.
"""
        result = filter_output(
            "rubocop",
            stdout,
            "",
            1,
            plan=plan_command("rubocop"),
        )
        self.assertEqual(result.filter_name, "rubocop")
        self.assertIn("rubocop: 2 offenses in 1 files", result.output)
        self.assertIn("Layout/TrailingWhitespace", result.output)

    def test_rspec_keeps_failure_blocks(self):
        stdout = """Failures:

  1) User saves to database
     Failure/Error: expect(user.save).to eq(true)
       expected: true
            got: false
     # ./spec/models/user_spec.rb:11:in `block (2 levels) in <top (required)>'

Failed examples:

rspec ./spec/models/user_spec.rb:10 # User saves to database

2 examples, 1 failure
"""
        result = filter_output(
            "rspec",
            stdout,
            "",
            1,
            plan=plan_command("rspec"),
        )
        self.assertEqual(result.filter_name, "rspec")
        self.assertIn("RSpec: 2 examples, 1 failure", result.output)
        self.assertIn("User saves to database", result.output)
        self.assertIn("expected: true", result.output)
