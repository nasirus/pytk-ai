import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command
from pytk_ai.plan.normalize import infer_filter_hint


class FiltersPhase2Tests(unittest.TestCase):
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

    def test_mypy_groups_diagnostics_by_file(self):
        stdout = """src/app.py:10: error: Incompatible return value type (got "str", expected "int")  [return-value]
src/app.py:12: note: Revealed type is "builtins.str"
src/lib.py:3: error: Name "missing" is not defined  [name-defined]
Found 2 errors in 2 files (checked 3 source files)
"""
        result = filter_output(
            "mypy src",
            stdout,
            "",
            1,
            plan=plan_command("mypy src"),
        )
        self.assertEqual(result.filter_name, "python.mypy")
        self.assertIn("mypy: 2 errors in 2 files", result.output)
        self.assertIn("[return-value]", result.output)
        self.assertIn('Revealed type is "builtins.str"', result.output)

    def test_pytest_keeps_failures_richer_than_summary_only(self):
        stdout = """============================= test session starts ==============================
collected 2 items

tests/test_app.py .F                                                    [100%]

=================================== FAILURES ===================================
_______________________________ test_failure _______________________________

    def test_failure():
>       assert 1 == 2
E       assert 1 == 2

tests/test_app.py:7: AssertionError
=========================== short test summary info ============================
FAILED tests/test_app.py::test_failure - assert 1 == 2
========================= 1 failed, 1 passed in 0.12s =========================
"""
        result = filter_output(
            "pytest -q",
            stdout,
            "",
            1,
            plan=plan_command("pytest -q"),
        )
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest:", result.output)
        self.assertIn("[FAIL] test_failure", result.output)
        self.assertIn("assert 1 == 2", result.output)

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

    def test_go_test_summarizes_failed_package_and_test(self):
        stdout = """ok  example.com/project/pkg/a 0.015s
--- FAIL: TestThing (0.00s)
    thing_test.go:12: expected 2, got 1
FAIL
FAIL    example.com/project/pkg/b  0.023s
"""
        result = filter_output(
            "go test ./...",
            stdout,
            "",
            1,
            plan=plan_command("go test ./..."),
        )
        self.assertEqual(result.filter_name, "go.test")
        self.assertIn("Go test: 1 packages passed, 1 packages failed", result.output)
        self.assertIn("[FAIL] TestThing", result.output)
        self.assertIn("expected 2, got 1", result.output)

    def test_non_test_build_vet_go_commands_keep_generic_output(self):
        result = filter_output(
            "go version",
            "go version go1.24.1 linux/amd64\n",
            "",
            0,
            plan=plan_command("go version"),
        )
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("go version go1.24.1 linux/amd64", result.output)

    def test_golangci_lint_groups_by_linter(self):
        stderr = """pkg/server/server.go:12:2: Error return value of `w.Write` is not checked (errcheck)
pkg/server/server.go:20:6: exported type Foo should have comment or be unexported [revive]
"""
        result = filter_output(
            "golangci-lint run",
            "",
            stderr,
            1,
            plan=plan_command("golangci-lint run"),
        )
        self.assertEqual(result.filter_name, "golangci-lint")
        self.assertIn("golangci-lint: 2 issues in 1 files", result.output)
        self.assertIn("errcheck", result.output)
        self.assertIn("revive", result.output)

    def test_rubocop_groups_offenses_by_file(self):
        stdout = """app/models/user.rb:10:5: C: Layout/TrailingWhitespace: Trailing whitespace detected.
app/models/user.rb:12:3: W: Lint/UselessAssignment: Useless assignment to variable - x.
"""
        result = filter_output(
            "rubocop",
            stdout,
            "",
            1,
            plan=plan_command("rubocop"),
        )
        self.assertEqual(result.filter_name, "rubocop")
        self.assertIn("rubocop: 2 offenses in 1 files", result.output)
        self.assertIn("Layout/TrailingWhitespace", result.output)

    def test_rspec_keeps_failure_blocks(self):
        stdout = """Failures:

  1) User saves to database
     Failure/Error: expect(user.save).to eq(true)
       expected: true
            got: false
     # ./spec/models/user_spec.rb:11:in `block (2 levels) in <top (required)>'

Failed examples:

rspec ./spec/models/user_spec.rb:10 # User saves to database

2 examples, 1 failure
"""
        result = filter_output(
            "rspec",
            stdout,
            "",
            1,
            plan=plan_command("rspec"),
        )
        self.assertEqual(result.filter_name, "rspec")
        self.assertIn("RSpec: 2 examples, 1 failure", result.output)
        self.assertIn("User saves to database", result.output)
        self.assertIn("expected: true", result.output)

    def test_infer_filter_hint_handles_phase2_commands(self):
        self.assertEqual(infer_filter_hint("cargo build"), "cargo")
        self.assertEqual(infer_filter_hint("eslint src"), "lint")
        self.assertEqual(infer_filter_hint("next build"), "next")
        self.assertEqual(infer_filter_hint("go test ./..."), "go")
        self.assertEqual(infer_filter_hint("bundle exec rspec"), "rspec")
        self.assertIsNone(infer_filter_hint("go version"))
