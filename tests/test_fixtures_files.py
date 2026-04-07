import re
import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesFilesTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("files", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_rg_matches(self):
        f, result = self._run("rg_matches")
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("matches in", result.output)
        self.assertIn("files", result.output)
        self.assertIn("main", result.output)

    def test_rg_error(self):
        f, result = self._run("rg_error")
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("regex parse error", result.output)

    def test_find_results(self):
        f, result = self._run("find_results")
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("13F 9D:", result.output)
        self.assertIn("config/ settings.py", result.output)
        self.assertIn("src/api/ auth.py router.py", result.output)
        self.assertIn("tests/unit/ test_auth.py test_jobs.py", result.output)
        self.assertIn("scripts/ migrate.py setup.py", result.output)

    def test_tree_output(self):
        f, result = self._run("tree_output")
        self.assertEqual(result.filter_name, "files.tree")
        self.assertIn("tree: 10 directories, 12 files", result.output)
        self.assertIn("├── README.md", result.output)
        self.assertIn("├── src", result.output)
        self.assertIn("... +", result.output)

    def test_wc_multi(self):
        f, result = self._run("wc_multi")
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn("wc total:", result.output)
        self.assertIn("268 lines", result.output)
        self.assertIn("src/app.py: 202 lines, 347 words, 3114 bytes", result.output)
        self.assertIn(
            "tests/test_app.py: 66 lines, 126 words, 1237 bytes", result.output
        )

    def test_diff_unified(self):
        f, result = self._run("diff_unified")
        add_count = sum(
            1
            for line in f["stdout"].splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        delete_count = sum(
            1
            for line in f["stdout"].splitlines()
            if line.startswith("-") and not line.startswith("---")
        )
        label = re.search(r"^\+\+\+ (\S+)", f["stdout"], re.MULTILINE)
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIsNotNone(label)
        self.assertIn(
            f"{label.group(1)} (+{add_count}/-{delete_count})",
            result.output,
        )
        self.assertIn("+ line 2 updated", result.output)
        self.assertIn("... +", result.output)
