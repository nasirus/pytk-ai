import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersRubyTests(unittest.TestCase):
    def test_rake_summarizes_passing_minitest_run(self):
        stdout = """Run options: --seed 12345

# Running:

....

Finished in 0.123456s, 32.4 runs/s

4 runs, 4 assertions, 0 failures, 0 errors, 1 skips
"""
        result = filter_output(
            "pytk-ai rake test",
            stdout,
            "",
            0,
            plan=plan_command("pytk-ai rake test"),
        )
        self.assertEqual(result.filter_name, "rake")
        self.assertEqual(result.output, "ok rake test: 4 runs, 0 failures, 1 skips")

    def test_rake_keeps_minitest_failure_details(self):
        stdout = """Run options: --seed 54321

# Running:

..F.E

Finished in 0.234567s, 21.3 runs/s

  1) Failure:
UserTest#test_valid [/tmp/test/models/user_test.rb:15]:
Expected: true
  Actual: false

  2) Error:
UserTest#test_loads [/tmp/test/models/user_test.rb:24]:
RuntimeError: boom
    /tmp/test/models/user_test.rb:24:in `test_loads'

5 runs, 4 assertions, 1 failures, 1 errors, 0 skips
"""
        result = filter_output(
            "pytk-ai rake test",
            stdout,
            "",
            1,
            plan=plan_command("pytk-ai rake test"),
        )
        self.assertEqual(result.filter_name, "rake")
        self.assertIn("rake test: 5 runs, 1 failures, 1 errors", result.output)
        self.assertIn("UserTest#test_valid", result.output)
        self.assertIn("Expected: true", result.output)
        self.assertIn("RuntimeError: boom", result.output)

    def test_rubocop_groups_offenses_by_file(self):
        stdout = """/tmp/demo/app/models/user.rb:1:1: C: Style/Documentation: Missing top-level documentation comment for `class User`.
/tmp/demo/app/models/user.rb:4:5: W: [Correctable] Lint/UselessAssignment: Useless assignment to variable - `x`.
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
        self.assertIn("app/models/user.rb (2)", result.output)
        self.assertIn("Style/Documentation", result.output)
        self.assertIn("Lint/UselessAssignment", result.output)

    def test_rubocop_json_reports_correctable_counts(self):
        stdout = """{
  "files": [
    {
      "path": "app/controllers/users_controller.rb",
      "offenses": [
        {
          "severity": "error",
          "message": "Syntax error, unexpected end-of-input.",
          "cop_name": "Lint/Syntax",
          "correctable": false,
          "location": {"start_line": 30}
        }
      ]
    },
    {
      "path": "app/models/user.rb",
      "offenses": [
        {
          "severity": "convention",
          "message": "Trailing whitespace detected.",
          "cop_name": "Layout/TrailingWhitespace",
          "correctable": true,
          "location": {"start_line": 10}
        }
      ]
    }
  ],
  "summary": {
    "offense_count": 2,
    "inspected_file_count": 20,
    "correctable_offense_count": 1
  }
}
"""
        result = filter_output(
            "rubocop",
            stdout,
            "",
            1,
            plan=plan_command("rubocop"),
        )
        self.assertEqual(result.filter_name, "rubocop")
        self.assertIn("rubocop: 2 offenses (20 files)", result.output)
        self.assertIn("app/controllers/users_controller.rb", result.output)
        self.assertIn(":30 Lint/Syntax", result.output)
        self.assertIn("(1 correctable, run `rubocop -A`)", result.output)

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

    def test_rspec_json_reports_duration_and_pending(self):
        stdout = """{
  "examples": [
    {
      "full_description": "User saves to database",
      "status": "failed",
      "file_path": "./spec/models/user_spec.rb",
      "line_number": 10,
      "exception": {
        "class": "RSpec::Expectations::ExpectationNotMetError",
        "message": "expected true but got false",
        "backtrace": [
          "/usr/local/lib/ruby/gems/3.2.0/gems/rspec-expectations/lib/rspec/fail.rb:1",
          "./spec/models/user_spec.rb:11:in `block (2 levels) in <top (required)>'"
        ]
      }
    },
    {
      "full_description": "User validates email format",
      "status": "pending",
      "file_path": "./spec/models/user_spec.rb",
      "line_number": 20,
      "exception": null
    }
  ],
  "summary": {
    "duration": 0.123,
    "example_count": 2,
    "failure_count": 1,
    "pending_count": 1,
    "errors_outside_of_examples_count": 0
  }
}
"""
        result = filter_output(
            "rspec",
            stdout,
            "",
            1,
            plan=plan_command("rspec"),
        )
        self.assertEqual(result.filter_name, "rspec")
        self.assertIn("RSpec: 0 passed, 1 failed, 1 pending (0.12s)", result.output)
        self.assertIn("❌ User saves to database", result.output)
        self.assertIn(
            "ExpectationNotMetError: expected true but got false", result.output
        )
        self.assertIn("./spec/models/user_spec.rb:11", result.output)
