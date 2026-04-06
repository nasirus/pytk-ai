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
        self.assertIn("clippy::unnecessary_map_or", result.output)
        self.assertIn("src/lib.rs:10:9", result.output)

    def test_cargo_clippy_keeps_error_details_separate(self):
        stderr = """Checking demo v0.1.0 (/tmp/demo)
error: struct literals are not allowed here
warning: this function has too many arguments [clippy::too_many_arguments]
 --> src/lib.rs:16:1
"""
        result = filter_output(
            "cargo clippy --all-targets",
            "",
            stderr,
            1,
            plan=plan_command("cargo clippy --all-targets"),
        )
        self.assertEqual(result.filter_name, "cargo.clippy")
        self.assertIn("cargo clippy: 1 errors, 1 warnings", result.output)
        self.assertIn("Error details:", result.output)
        self.assertIn("struct literals are not allowed here", result.output)
        self.assertIn("clippy::too_many_arguments", result.output)

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

    def test_cargo_install_summarizes_success_and_replacements(self):
        stdout = """Updating crates.io index
Installing cargo-watch 8.5.0
Compiling proc-macro2 v1.0.82
Compiling syn v2.0.66
Replaced package `cargo-watch v8.4.0` with `cargo-watch v8.5.0`
warning: be sure to add /home/demo/.cargo/bin to your PATH
Installed cargo-watch v8.5.0
"""
        result = filter_output(
            "cargo install cargo-watch",
            stdout,
            "",
            0,
            plan=plan_command("cargo install cargo-watch"),
        )
        self.assertEqual(result.filter_name, "cargo.install")
        self.assertIn(
            "cargo install (cargo-watch 8.5.0, 2 deps compiled)", result.output
        )
        self.assertIn("Replaced package `cargo-watch v8.4.0`", result.output)
        self.assertIn("be sure to add /home/demo/.cargo/bin", result.output)

    def test_cargo_install_reports_already_installed(self):
        stdout = "Ignored package `cargo-watch v8.5.0` is already installed, use --force to override\n"
        result = filter_output(
            "cargo install cargo-watch",
            stdout,
            "",
            0,
            plan=plan_command("cargo install cargo-watch"),
        )
        self.assertEqual(result.filter_name, "cargo.install")
        self.assertEqual(
            result.output, "cargo install: cargo-watch v8.5.0 already installed"
        )

    def test_cargo_install_groups_errors(self):
        stderr = """Installing cargo-watch 8.5.0
Compiling proc-macro2 v1.0.82
error[E0425]: cannot find value `missing` in this scope
 --> src/main.rs:2:5
  |
2 |     missing();
  |     ^^^^^^^ not found in this scope
"""
        result = filter_output(
            "cargo install cargo-watch",
            "",
            stderr,
            101,
            plan=plan_command("cargo install cargo-watch"),
        )
        self.assertEqual(result.filter_name, "cargo.install")
        self.assertIn(
            "cargo install: 1 errors (cargo-watch 8.5.0, 1 deps compiled)",
            result.output,
        )
        self.assertIn("error[E0425]: cannot find value `missing`", result.output)

    def test_cargo_nextest_summarizes_clean_run(self):
        stdout = """Compiling demo v0.1.0 (/tmp/demo)
Starting 12 tests across 3 binaries
PASS [   0.010s] demo::tests::alpha
Summary [   0.123s] 12 tests run: 12 passed, 2 skipped
"""
        result = filter_output(
            "cargo nextest run",
            stdout,
            "",
            0,
            plan=plan_command("cargo nextest run"),
        )
        self.assertEqual(result.filter_name, "cargo.nextest")
        self.assertEqual(
            result.output, "cargo nextest: 12 passed, 2 skipped (3 binaries, 0.123s)"
        )

    def test_cargo_nextest_keeps_failures_and_summary(self):
        stderr = """Starting 8 tests across 2 binaries
FAIL [   0.020s] demo::tests::broken
--- STDOUT:              demo::tests::broken ---
assertion failed: left == right
Cancelling due to test failure
Summary [   0.250s] 8 tests run: 6 passed, 1 failed, 1 skipped
FAIL [   0.020s] duplicate recap after summary
error: test run failed
"""
        result = filter_output(
            "cargo nextest run",
            "",
            stderr,
            100,
            plan=plan_command("cargo nextest run"),
        )
        self.assertEqual(result.filter_name, "cargo.nextest")
        self.assertIn("FAIL [   0.020s] demo::tests::broken", result.output)
        self.assertIn("assertion failed: left == right", result.output)
        self.assertIn("Cancelling due to test failure", result.output)
        self.assertIn(
            "cargo nextest: 6 passed, 1 failed, 1 skipped (2 binaries, 0.250s)",
            result.output,
        )
        self.assertNotIn("duplicate recap", result.output)

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

    def test_biome_block_output_keeps_diagnostics_and_strips_noise(self):
        stderr = """Checked 42 files in 0.5s

src/app.tsx:5:3 lint/suspicious/noExplicitAny ━━━━━━━━━━━━━━━━━━━━
  × Unexpected any. Specify a different type.
  3 │ interface Props {
  4 │   data: any;
  5 │         ^^^

Found 1 error.
"""
        result = filter_output(
            "biome check src",
            "",
            stderr,
            1,
            plan=plan_command("biome check src"),
        )
        self.assertEqual(result.filter_name, "lint.biome")
        self.assertNotIn("Checked 42 files", result.output)
        self.assertIn("src/app.tsx:5:3 lint/suspicious/noExplicitAny", result.output)
        self.assertIn("Found 1 error.", result.output)

    def test_prettier_check_uses_formatter_summary(self):
        stderr = """Checking formatting...
[warn] src/app.ts
[warn] tests/app.test.ts
[warn] Code style issues found in 2 files. Run Prettier with --write to fix.
"""
        result = filter_output(
            "prettier --check .",
            "",
            stderr,
            1,
            plan=plan_command("prettier --check ."),
        )
        self.assertEqual(result.filter_name, "format.prettier")
        self.assertIn("Format (prettier): 2 files need formatting", result.output)
        self.assertIn("app.ts", result.output)

    def test_black_check_uses_formatter_summary(self):
        stderr = """would reformat: src/main.py
would reformat: tests/test_utils.py
Oh no! 💥 💔 💥
2 files would be reformatted, 3 files would be left unchanged.
"""
        result = filter_output(
            "black --check .",
            "",
            stderr,
            1,
            plan=plan_command("black --check ."),
        )
        self.assertEqual(result.filter_name, "format.black")
        self.assertIn("Format (black): 2 files need formatting", result.output)
        self.assertIn("3 files already formatted", result.output)

    def test_biome_format_empty_success_returns_ok(self):
        result = filter_output(
            "biome format src",
            "",
            "",
            0,
            plan=plan_command("biome format src"),
        )
        self.assertEqual(result.filter_name, "format.biome")
        self.assertEqual(result.output, "biome: ok")

    def test_biome_check_fix_routes_to_format_summary(self):
        stdout = """Formatted src/app.ts
Formatted src/lib.ts
Checked 2 files in 5ms
"""
        result = filter_output(
            "biome check --write src",
            stdout,
            "",
            0,
            plan=plan_command("biome check --write src"),
        )
        self.assertEqual(result.filter_name, "format.biome")
        self.assertIn("Format (biome): 2 files formatted", result.output)
        self.assertIn("src/app.ts", result.output)

    def test_prettier_write_lists_formatted_files(self):
        stdout = """src/app.ts 12ms
tests/app.test.ts 3ms
"""
        result = filter_output(
            "prettier --write .",
            stdout,
            "",
            0,
            plan=plan_command("prettier --write ."),
        )
        self.assertEqual(result.filter_name, "format.prettier")
        self.assertIn("Format (prettier): 2 files formatted", result.output)
        self.assertIn("src/app.ts", result.output)

    def test_wrapper_prettier_command_uses_format_filter(self):
        stderr = """Checking formatting...
[warn] src/app.ts
[warn] Code style issues found in 1 file. Run Prettier with --write to fix.
"""
        result = filter_output(
            "pnpm exec prettier --check src/app.ts",
            "",
            stderr,
            1,
            plan=plan_command("pnpm exec prettier --check src/app.ts"),
        )
        self.assertEqual(result.filter_name, "format.prettier")
        self.assertIn("1 files need formatting", result.output)

    def test_pytk_format_detected_ruff_command_uses_ruff_formatter_summary(self):
        stdout = """Would reformat: src/app.py
Would reformat: tests/test_app.py
2 files would be reformatted, 3 files left unchanged
"""
        result = filter_output(
            "ruff format --check .",
            stdout,
            "",
            1,
        )
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("Ruff format: 2 files need formatting", result.output)

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
