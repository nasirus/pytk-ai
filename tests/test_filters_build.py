import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersBuildTests(unittest.TestCase):
    def test_non_test_cargo_commands_do_not_use_test_filter(self):
        stderr = """error[E0425]: cannot find value `missing` in this scope
 --> src/main.rs:2:5
  |
2 |     missing();
  |     ^^^^^^^ not found in this scope
"""
        result = filter_output(
            "cargo build",
            "",
            stderr,
            101,
            plan=plan_command("cargo build"),
        )
        self.assertEqual(result.filter_name, "cargo.build")
        self.assertIn("cannot find value", result.output)

    def test_cargo_build_groups_rustc_errors(self):
        stderr = """Compiling demo v0.1.0 (/tmp/demo)
error[E0425]: cannot find value `missing` in this scope
 --> src/main.rs:2:5
  |
2 |     missing();
  |     ^^^^^^^ not found in this scope

warning: unused variable: `x`
 --> src/lib.rs:4:9
  |
4 |     let x = 1;
  |         ^ help: if this is intentional, prefix it with an underscore: `_x`
"""
        result = filter_output(
            "cargo build",
            "",
            stderr,
            101,
            plan=plan_command("cargo build"),
        )
        self.assertEqual(result.filter_name, "cargo.build")
        self.assertIn("cargo build: 1 errors, 1 warnings", result.output)
        self.assertIn("src/main.rs", result.output)
        self.assertIn("E0425", result.output)

    def test_cargo_clippy_groups_warnings(self):
        stderr = """warning: this `map_or` can be simplified
 --> src/lib.rs:10:9
  |
  = help: for further information visit https://rust-lang.github.io/rust-clippy/master/index.html#unnecessary_map_or
"""
        result = filter_output(
            "cargo clippy --all-targets",
            "",
            stderr,
            1,
            plan=plan_command("cargo clippy --all-targets"),
        )
        self.assertEqual(result.filter_name, "cargo.clippy")
        self.assertIn("cargo clippy: 0 errors, 1 warnings", result.output)
        self.assertIn("src/lib.rs", result.output)

    def test_cargo_fmt_check_lists_reformat_targets(self):
        stdout = """Would reformat: src/lib.rs
Would reformat: tests/test_app.rs
"""
        result = filter_output(
            "cargo fmt --check",
            stdout,
            "",
            1,
            plan=plan_command("cargo fmt --check"),
        )
        self.assertEqual(result.filter_name, "cargo.fmt")
        self.assertIn("2 files need formatting", result.output)
        self.assertIn("src/lib.rs", result.output)

    def test_eslint_stylish_output_is_grouped(self):
        stdout = """/repo/src/app.ts
  1:7  error    'value' is assigned a value but never used  @typescript-eslint/no-unused-vars
  4:1  warning  Unexpected console statement                no-console

/repo/src/lib.ts
  2:3  error  Missing return type on function  @typescript-eslint/explicit-function-return-type
"""
        result = filter_output(
            "eslint src",
            stdout,
            "",
            1,
            plan=plan_command("eslint src"),
        )
        self.assertEqual(result.filter_name, "lint.eslint")
        self.assertIn("ESLint: 2 errors, 1 warnings in 2 files", result.output)
        self.assertIn("Top rules:", result.output)
        self.assertIn("src/app.ts", result.output)

    def test_biome_output_is_grouped(self):
        stderr = """src/app.ts:3:1 error lint/style/useConst This variable is never reassigned.
src/app.ts:7:5 warning lint/suspicious/noConsoleLog Avoid console.log in production.
"""
        result = filter_output(
            "biome lint src",
            "",
            stderr,
            1,
            plan=plan_command("biome lint src"),
        )
        self.assertEqual(result.filter_name, "lint.biome")
        self.assertIn("Biome: 1 errors, 1 warnings in 1 files", result.output)
        self.assertIn("useConst", result.output)

    def test_tsc_output_is_grouped_by_file(self):
        stderr = """src/app.ts(10,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/app.ts(12,7): error TS2345: Argument of type 'number' is not assignable to parameter of type 'string'.
  The expected type comes from the function signature.
"""
        result = filter_output(
            "tsc --noEmit",
            "",
            stderr,
            2,
            plan=plan_command("tsc --noEmit"),
        )
        self.assertEqual(result.filter_name, "tsc")
        self.assertIn("TypeScript: 2 errors in 1 files", result.output)
        self.assertIn("TS2322", result.output)
        self.assertIn(
            "expected type comes from the function signature", result.output.lower()
        )

    def test_next_build_extracts_routes_and_sizes(self):
        stdout = """▲ Next.js 15.2.0
Creating an optimized production build ...
✓ Compiled successfully in 12.4s
Route (app)                    Size     First Load JS
┌ ○ /                          1.2 kB        132 kB
├ ● /dashboard                 2.5 kB        156 kB
└ ○ /api/auth                  0.5 kB         89 kB
"""
        result = filter_output(
            "next build",
            stdout,
            "",
            0,
            plan=plan_command("next build"),
        )
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("3 routes (2 static, 1 dynamic)", result.output)
        self.assertIn("/dashboard", result.output)
        self.assertIn("Time: 12.4s", result.output)

    def test_next_build_failure_keeps_raw_diagnostics(self):
        stderr = """Failed to compile.

./src/app/page.tsx:7:12
Type error: Type 'string' is not assignable to type 'number'.
"""
        result = filter_output(
            "next build",
            "",
            stderr,
            1,
            plan=plan_command("next build"),
        )
        self.assertEqual(result.filter_name, "next.build")
        self.assertIn("Failed to compile.", result.output)
        self.assertIn("./src/app/page.tsx:7:12", result.output)
        self.assertIn("Type error:", result.output)
