import unittest

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
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertLess(len(result.output), len(f["stdout"]))
        self.assertIn("abc1234", result.output)
        self.assertIn("Add planner coverage", result.output)
        self.assertNotIn("Author:", result.output)

    def test_diff_multifile(self):
        f, result = self._run("diff_multifile")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("src/app.py (+2/-1)", result.output)
        self.assertIn("+ new = 2", result.output)
        self.assertNotIn("@@", result.output)

    def test_commit_success(self):
        f, result = self._run("commit_success")
        self.assertEqual(result.filter_name, "git.commit")
        self.assertIn("abc1234", result.output)
        self.assertIn("ok", result.output)

    def test_pull_fastforward(self):
        f, result = self._run("pull_fastforward")
        self.assertEqual(result.filter_name, "git.pull")
        self.assertEqual(result.output, "ok 1 files +6 -2")

    def test_branch_vv(self):
        f, result = self._run("branch_vv")
        self.assertEqual(result.filter_name, f["filter_name"])
        self.assertIn("feature/login 1234567", result.output)
        self.assertIn("* main", result.output)

    def test_add_warning(self):
        f, result = self._run("add_warning")
        self.assertEqual(result.filter_name, "git.add")
        self.assertIn("warning: adding embedded git repository", result.output)

    def test_show_failure(self):
        f, result = self._run("show_failure")
        self.assertEqual(result.filter_name, "git.show")
        self.assertIn("fatal:", result.output)

    def test_status_dirty(self):
        f, result = self._run("status_dirty")
        self.assertEqual(result.filter_name, "git.status")
        self.assertLess(len(result.output), len(f["stdout"]))
        self.assertIn("modified:", result.output)

    def test_output_shorter_than_input(self):
        """Every successful git fixture should produce shorter output."""
        for name in ("log_full", "diff_multifile", "status_dirty"):
            with self.subTest(name=name):
                f, result = self._run(name)
                self.assertLess(len(result.output), len(f["stdout"]))
