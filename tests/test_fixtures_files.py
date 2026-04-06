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
        self.assertIn("40F 13D:", result.output)
        self.assertIn("./ README.md", result.output)
        self.assertIn("ext: .py(39) .md(1)", result.output)

    def test_tree_output(self):
        f, result = self._run("tree_output")
        self.assertEqual(result.filter_name, "files.tree")
        self.assertIn("2 directories, 3 files", result.output)
        self.assertIn("├── src", result.output)

    def test_wc_multi(self):
        f, result = self._run("wc_multi")
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn("wc total:", result.output)
        self.assertIn("500 lines", result.output)

    def test_diff_unified(self):
        f, result = self._run("diff_unified")
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIn("b.txt (+2/-1)", result.output)
        self.assertIn("+ new", result.output)
