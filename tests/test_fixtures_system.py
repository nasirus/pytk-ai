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
        self.assertIn("repeated line omitted 3 time(s)", result.output)

    def test_cat_missing(self):
        f, result = self._run("cat_missing")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertIn("No such file or directory", result.output)

    def test_cat_tailwind(self):
        f, result = self._run("cat_tailwind")
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertEqual(result.output, "same\nsame\nsame\nsame")
