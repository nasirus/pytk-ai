import unittest

from ptk.plan.normalize import (
    has_disabled_prefix,
    infer_filter_hint,
    normalize_absolute_first_token,
    rewrite_line_range,
    strip_env_prefix,
    strip_trailing_redirect_suffix,
)


class PlanNormalizeTests(unittest.TestCase):
    def test_strip_env_prefix_keeps_prefix_and_command(self):
        prefix, command = strip_env_prefix('FOO=1 BAR="two words" git status')
        self.assertEqual(prefix, 'FOO=1 BAR="two words" ')
        self.assertEqual(command, "git status")

    def test_normalize_absolute_first_token_uses_basename(self):
        self.assertEqual(
            normalize_absolute_first_token("/usr/bin/git status"),
            "git status",
        )

    def test_strip_trailing_redirect_suffix_preserves_suffix(self):
        command, suffix = strip_trailing_redirect_suffix("git status > out.txt 2>&1")
        self.assertEqual(command, "git status")
        self.assertEqual(suffix, " > out.txt 2>&1")

    def test_rewrite_line_range_handles_head_and_tail(self):
        self.assertEqual(
            rewrite_line_range("head -5 README.md"),
            "ptk read README.md --max-lines 5",
        )
        self.assertEqual(
            rewrite_line_range("tail --lines 7 README.md"),
            "ptk read README.md --tail-lines 7",
        )

    def test_has_disabled_prefix_detects_ptk_and_rtk_flags(self):
        self.assertTrue(has_disabled_prefix("PTK_DISABLED=1 git status"))
        self.assertTrue(has_disabled_prefix("RTK_DISABLED=1 git status"))

    def test_infer_filter_hint_handles_ptk_and_python_forms(self):
        self.assertEqual(infer_filter_hint("ptk git status"), "git")
        self.assertEqual(infer_filter_hint("python -m pytest -q"), "pytest")
