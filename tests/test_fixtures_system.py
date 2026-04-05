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
        self.assertIn("INFO", result.output)
        self.assertIn("ERROR", result.output)

    def test_cat_missing(self):
        f, result = self._run("cat_missing")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertIn("No such file or directory", result.output)

    def test_cat_tailwind(self):
        f, result = self._run("cat_tailwind")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertEqual(result.output, "same\nsame\nsame\nsame")

    def test_ls_la(self):
        f, result = self._run("ls_la")
        self.assertEqual(result.filter_name, "system.ls")
        self.assertIn("src/", result.output)
        self.assertIn("tests/", result.output)
        self.assertIn("Cargo.toml  1.2K", result.output)
        self.assertIn("README.md  5.5K", result.output)
        self.assertNotIn(".git/", result.output)
        self.assertNotIn("node_modules", result.output)
        self.assertNotIn("__pycache__", result.output)
        self.assertNotIn(".vscode", result.output)
        self.assertNotIn("drwx", result.output)
        self.assertIn(".gitignore", result.output)
        self.assertIn("link -> target", result.output)
