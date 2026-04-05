import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesBuildTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("build", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_cargo_build_error(self):
        f, result = self._run("cargo_build_error")
        self.assertEqual(result.filter_name, "cargo.build")
        self.assertIn("cargo build: 1 errors, 1 warnings", result.output)
        self.assertIn("E0425", result.output)

    def test_cargo_clippy(self):
        f, result = self._run("cargo_clippy")
        self.assertEqual(result.filter_name, "cargo.clippy")
        self.assertIn("cargo clippy: 0 errors, 1 warnings", result.output)

    def test_cargo_fmt_check(self):
        f, result = self._run("cargo_fmt_check")
        self.assertEqual(result.filter_name, "cargo.fmt")
        self.assertIn("files need formatting", result.output)

    def test_eslint_stylish(self):
        f, result = self._run("eslint_stylish")
        self.assertEqual(result.filter_name, "lint.eslint")
        self.assertIn("errors", result.output)
        self.assertIn("warnings", result.output)

    def test_biome_lint(self):
        f, result = self._run("biome_lint")
        self.assertEqual(result.filter_name, "lint.biome")
        self.assertIn("errors", result.output)
        self.assertIn("warnings", result.output)

    def test_tsc_errors(self):
        f, result = self._run("tsc_errors")
        self.assertEqual(result.filter_name, "tsc")
        self.assertIn("errors", result.output)
        self.assertIn("TS", result.output)

    def test_next_build_ok(self):
        f, result = self._run("next_build_ok")
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("3 routes", result.output)
        self.assertIn("Time: 12.4s", result.output)

    def test_next_build_fail(self):
        f, result = self._run("next_build_fail")
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("Failed to compile.", result.output)
        self.assertIn("Type error:", result.output)
