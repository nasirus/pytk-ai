import unittest

from ptk.filters import filter_output
from ptk.filters.generic import filter_generic_output
from ptk.plan import plan_command


class FiltersGenericTests(unittest.TestCase):
    def test_generic_filter_removes_ansi_and_truncates(self):
        result = filter_generic_output(
            "echo test",
            "\x1b[31mred\x1b[0m\n1\n2\n3\n4",
            "",
            0,
            max_output_lines=3,
        )
        self.assertEqual(result.filter_name, "generic")
        self.assertNotIn("\x1b", result.output)
        self.assertIn("more lines omitted", result.output)

    def test_filter_output_uses_plan_hint_first(self):
        plan = plan_command("git status")
        result = filter_output(
            "git status",
            'On branch main\n  (use "git add" to track)\n',
            "",
            0,
            plan=plan,
        )
        self.assertEqual(result.filter_name, "git.status")
        self.assertNotIn('(use "git add"', result.output)

    def test_filter_output_falls_back_when_specific_filter_raises(self):
        plan = plan_command("git status")
        import ptk.filters as filters_module

        original = filters_module._FILTERS["git"]
        try:

            def boom(*args, **kwargs):
                raise RuntimeError("boom")

            filters_module._FILTERS["git"] = boom
            result = filter_output("git status", "ok", "", 0, plan=plan)
        finally:
            filters_module._FILTERS["git"] = original

        self.assertEqual(result.filter_name, "generic")
        self.assertIn("filter failed", result.error)
