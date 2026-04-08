import unittest
import re

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesGitTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("git", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_log_full(self):
        f, result = self._run("log_full")
        commits = re.findall(r"^commit ([0-9a-f]{7,40})$", f["stdout"], re.MULTILINE)
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertLess(len(result.output), len(f["stdout"]))
        self.assertGreaterEqual(len(commits), 2)
        self.assertIn(commits[0][:7], result.output)
        self.assertIn("Document fixture capture workflow", result.output)
        self.assertIn("Normalize runner input before execution", result.output)
        self.assertNotIn("Author:", result.output)

    def test_diff_multifile(self):
        f, result = self._run("diff_multifile")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("src/app.py (+2/-1)", result.output)
        self.assertIn("+ new = 2", result.output)
        self.assertNotIn("@@", result.output)

    def test_commit_success(self):
        f, result = self._run("commit_success")
        match = re.search(
            r"^\[[^\]]+ ([0-9a-f]{7,})\] Add compact filter$", f["stdout"], re.MULTILINE
        )
        self.assertEqual(result.filter_name, "git.commit")
        self.assertIsNotNone(match)
        self.assertIn(match.group(1)[:7], result.output)
        self.assertIn("ok", result.output)

    def test_pull_fastforward(self):
        f, result = self._run("pull_fastforward")
        match = re.search(
            r"(\d+)\s+files? changed(?:,\s+(\d+)\s+insertions?\(\+\))?(?:,\s+(\d+)\s+deletions?\(-\))?",
            f["stdout"],
        )
        self.assertEqual(result.filter_name, "git.pull")
        self.assertIsNotNone(match)
        self.assertEqual(
            result.output,
            f"ok {match.group(1)} files +{match.group(2) or '0'} -{match.group(3) or '0'}",
        )

    def test_branch_vv(self):
        f, result = self._run("branch_vv")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("feature/login", result.output)
        self.assertIn("feature/search", result.output)
        self.assertIn("release/1.0", result.output)
        self.assertIn("* main", result.output)
        self.assertRegex(result.output, r"\b[0-9a-f]{7}\b")

    def test_add_warning(self):
        f, result = self._run("add_warning")
        self.assertEqual(result.filter_name, "git.add")
        self.assertEqual(result.output, "ok")

    def test_show_failure(self):
        f, result = self._run("show_failure")
        self.assertEqual(result.filter_name, "git.show")
        self.assertIn("fatal:", result.output)

    def test_status_dirty(self):
        f, result = self._run("status_dirty")
        self.assertEqual(result.filter_name, "git.status")
        self.assertLess(len(result.output), len(f["stdout"]))
        self.assertIn("~ Modified:", result.output)
        self.assertIn("? Untracked:", result.output)

    def test_output_shorter_than_input(self):
        """Every successful git fixture should produce shorter output."""
        for name in ("log_full", "diff_multifile", "status_dirty"):
            with self.subTest(name=name):
                f, result = self._run(name)
                self.assertLess(len(result.output), len(f["stdout"]))
