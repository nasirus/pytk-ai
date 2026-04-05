import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersSystemTests(unittest.TestCase):
    def test_tail_deduplicates_repeated_lines(self):
        stdout = "tick\nsame\nsame\nsame\nsame\nend\n"
        result = filter_output(
            "tail server.log", stdout, "", 0, plan=plan_command("tail server.log")
        )
        self.assertEqual(result.filter_name, "system.read.tail")
        self.assertIn("repeated line omitted 3 time(s)", result.output)

    def test_cat_failure_preserves_raw_error(self):
        stderr = "cat: missing.txt: No such file or directory\n"
        result = filter_output(
            "cat missing.txt", "", stderr, 1, plan=plan_command("cat missing.txt")
        )
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertIn("No such file or directory", result.output)

    def test_cat_filename_containing_tail_does_not_collapse_lines(self):
        stdout = "same\nsame\nsame\nsame\n"
        result = filter_output(
            "cat tailwind.config.js",
            stdout,
            "",
            0,
            plan=plan_command("cat tailwind.config.js"),
        )
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertEqual(result.output, "same\nsame\nsame\nsame")

    def test_tail_collapses_repeated_lines(self):
        stdout = "tick\nsame\nsame\nsame\nsame\nend\n"
        result = filter_output(
            "tail app.log", stdout, "", 0, plan=plan_command("tail app.log")
        )
        self.assertEqual(result.filter_name, "system.read.tail")
        self.assertIn("repeated line omitted 3 time(s)", result.output)
