import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesGoTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("go", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_go_test_fail(self):
        f, result = self._run("go_test_fail")
        self.assertEqual(result.filter_name, "go.test")
        self.assertIn("Go test: 3 packages passed, 1 packages failed", result.output)
        self.assertIn("example.com/go-fixture/pkg/auth (3 failed)", result.output)
        self.assertIn("[FAIL] TestValidateEmail", result.output)
        self.assertIn('expected missing, got ""', result.output)

    def test_golangci_lint(self):
        f, result = self._run("golangci_lint")
        self.assertEqual(result.filter_name, "golangci-lint")
        self.assertIn("golangci-lint:", result.output)
        self.assertIn("issues", result.output)
