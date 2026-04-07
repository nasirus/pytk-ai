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
        self.assertIn("(4 crates)", result.output)
        self.assertIn("Top codes: E0425 (1x)", result.output)
        self.assertIn("src/lib.rs", result.output)
        self.assertIn("src/main.rs", result.output)
        self.assertIn("E0425", result.output)

    def test_cargo_clippy(self):
        f, result = self._run("cargo_clippy")
        self.assertEqual(result.filter_name, "cargo.clippy")
        self.assertIn("cargo clippy: 0 errors, 3 warnings (6 crates)", result.output)
        self.assertIn("clippy::unnecessary_map_or (1x)", result.output)
        self.assertIn("clippy::get_first (1x)", result.output)
        self.assertIn("clippy::useless_vec (1x)", result.output)
        self.assertIn("src/lib.rs:5:5", result.output)
        self.assertIn("src/lib.rs:12:5", result.output)
        self.assertIn("tests/clippy.rs:3:19", result.output)

    def test_cargo_fmt_check(self):
        f, result = self._run("cargo_fmt_check")
        self.assertEqual(result.filter_name, "cargo.fmt")
        self.assertIn("cargo fmt: 6 files need formatting", result.output)
        self.assertIn("examples/demo.rs", result.output)
        self.assertIn("src/handlers/api.rs", result.output)
        self.assertIn("src/models/user.rs", result.output)

    def test_eslint_stylish(self):
        f, result = self._run("eslint_stylish")
        self.assertEqual(result.filter_name, "lint.eslint")
        self.assertIn("ESLint: 10 errors, 13 warnings in 5 files", result.output)
        self.assertIn("Top rules: no-console (6x)", result.output)
        self.assertIn("src/app.js", result.output)
        self.assertIn("src/validators.js", result.output)

    def test_biome_lint(self):
        f, result = self._run("biome_lint")
        self.assertEqual(result.filter_name, "lint.biome")
        self.assertIn("Found 2 errors.", result.output)
        self.assertIn("Found 5 warnings.", result.output)
        self.assertIn("src/app.ts:4:12", result.output)
        self.assertIn("src/feature.ts:3:30", result.output)
        self.assertIn("lint/suspicious/noExplicitAny", result.output)

    def test_tsc_errors(self):
        f, result = self._run("tsc_errors")
        self.assertEqual(result.filter_name, "tsc")
        self.assertIn("TypeScript: 11 errors in 6 files", result.output)
        self.assertIn("Top codes: TS2322 (5x), TS2741 (2x)", result.output)
        self.assertIn("src/app.ts (3)", result.output)
        self.assertIn("types/flags.ts (1)", result.output)

    def test_next_build_ok(self):
        f, result = self._run("next_build_ok")
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("4 routes (4 static, 0 dynamic)", result.output)
        self.assertIn("/_not-found", result.output)
        self.assertIn("/dashboard", result.output)
        self.assertIn("/settings", result.output)
        self.assertIn("Errors: 0 | Warnings: 0", result.output)

    def test_next_build_fail(self):
        f, result = self._run("next_build_fail")
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("Creating an optimized production build", f["stdout"])
        self.assertIn("Failed to compile.", result.output)
        self.assertIn("./app/page.tsx:2:9", result.output)
        self.assertIn("Type error:", result.output)
