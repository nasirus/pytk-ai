import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesSystemTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("system", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_tail_repeated(self):
        f, result = self._run("tail_repeated")
        self.assertEqual(result.filter_name, "system.read.tail")
        self.assertIn("... repeated line omitted", result.output)
        self.assertIn("INFO", result.output)
        self.assertIn("ERROR", result.output)

    def test_cat_missing(self):
        f, result = self._run("cat_missing")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertIn("No such file or directory", result.output)

    def test_cat_tailwind(self):
        f, result = self._run("cat_tailwind")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertEqual(result.output, f["stdout"].rstrip())

    def test_ls_la(self):
        f, result = self._run("ls_la")
        self.assertEqual(result.filter_name, "system.ls")
        self.assertIn("docs/", result.output)
        self.assertIn("src/", result.output)
        self.assertIn("tests/", result.output)
        self.assertIn("Cargo.toml  49B", result.output)
        self.assertIn("README.md  26B", result.output)
        self.assertIn("pyproject.toml  41B", result.output)
        self.assertIn("setup.py  15B", result.output)
        self.assertIn("latest -> README.md", result.output)
        self.assertNotIn(".git/", result.output)
        self.assertNotIn("node_modules", result.output)
        self.assertNotIn("__pycache__", result.output)
        self.assertNotIn(".vscode", result.output)
        self.assertNotIn("drwx", result.output)
        self.assertIn("4 files, 3 dirs, 1 symlink", result.output)
        self.assertIn(".toml 2", result.output)
