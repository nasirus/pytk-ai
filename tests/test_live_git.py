"""Live execution tests against a real temporary git repository."""

import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from tests.helpers import requires_tool
except ImportError:
    from helpers import requires_tool
from pytk_ai.runner import run_command


@requires_tool("git")
class LiveGitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ptk-live-git-")
        cls.repo = Path(cls._tmpdir.name)

        def git(*args):
            subprocess.run(
                ["git", *args],
                cwd=cls.repo,
                capture_output=True,
                check=True,
            )

        git("init", "-q", "-b", "main")
        git("config", "user.email", "test@ptk.dev")
        git("config", "user.name", "PTK Test")

        # Create initial commit
        tracked = cls.repo / "tracked.txt"
        tracked.write_text("original content\n")
        git("add", "tracked.txt")
        git("commit", "-qm", "initial commit")

        # Create dirty state: modified tracked + untracked
        tracked.write_text("modified content\n")
        (cls.repo / "untracked.txt").write_text("new file\n")

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_git_status(self):
        result = run_command("git status", cwd=str(self.repo))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "git.status")
        self.assertEqual(result.executed_command, "git status --porcelain=v1 --branch")
        self.assertIn("M tracked.txt", result.filtered_output)
        self.assertIn("? untracked.txt", result.filtered_output)

    def test_git_log(self):
        result = run_command("git log --oneline", cwd=str(self.repo))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "git.log")
        self.assertIn("initial commit", result.filtered_output)

    def test_git_diff(self):
        result = run_command("git diff", cwd=str(self.repo))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "git.diff")
        self.assertIn("tracked.txt", result.filtered_output)

    def test_git_branch(self):
        result = run_command("git branch", cwd=str(self.repo))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "git.branch")
        self.assertIn("main", result.filtered_output)

    def test_git_show_nonexistent_ref_fails(self):
        result = run_command("git show nonexistent_ref_xyz", cwd=str(self.repo))
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "git.show")
        self.assertIn("fatal:", result.filtered_output)
