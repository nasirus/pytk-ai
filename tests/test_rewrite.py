import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ptk.rewrite import rewrite_command, rewrite_exit_code


class RewriteTests(unittest.TestCase):
    def test_rewrite_git_status(self):
        result = rewrite_command("git status")
        self.assertIsNotNone(result)
        self.assertEqual(result.output, "ptk git status")
        self.assertTrue(result.changed)

    def test_rewrite_compound_commands(self):
        result = rewrite_command("git add . && cargo test")
        self.assertIsNotNone(result)
        self.assertEqual(result.output, "ptk git add . && ptk cargo test")

    def test_rewrite_pipe_preserves_right_side(self):
        result = rewrite_command("git log | head")
        self.assertIsNotNone(result)
        self.assertEqual(result.output, "ptk git log | head")

    def test_no_rewrite_for_unsupported_command(self):
        code, rewritten = rewrite_exit_code("htop")
        self.assertEqual(code, 1)
        self.assertIsNone(rewritten)

    def test_already_ptk_passes_through(self):
        result = rewrite_command("ptk git status")
        self.assertIsNotNone(result)
        self.assertEqual(result.output, "ptk git status")
        self.assertFalse(result.changed)
