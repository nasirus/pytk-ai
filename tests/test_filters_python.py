import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersPythonTests(unittest.TestCase):
    def test_ruff_check_text_output_is_grouped(self):
        stdout = """src/app.py:1:1: F401 `os` imported but unused
src/app.py:5:1: E402 module level import not at top of file
src/lib/util.py:3:7: F401 `sys` imported but unused
"""
        result = filter_output(
            "ruff check .",
            stdout,
            "",
            1,
            plan=plan_command("ruff check ."),
        )
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("Ruff: 3 issues in 2 files", result.output)
        self.assertIn("F401 (2x)", result.output)
        self.assertIn("src/app.py", result.output)

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
collected 5 items

.F..F                                                                    [100%]

=================================== FAILURES ===================================
_______________________________ test_divide_fail _______________________________

    def test_divide_fail():
>       assert divide(5, 2) == 3
E       assert 2.5 == 3
E        +  where 2.5 = divide(5, 2)

tests/test_math.py:9: AssertionError
________________________________ test_contains _________________________________

    def test_contains():
>       assert "pytest" in "python"
E       AssertionError: assert 'pytest' in 'python'

tests/test_strings.py:7: AssertionError
=========================== short test summary info ============================
FAILED tests/test_math.py::test_divide_fail - assert 2.5 == 3
FAILED tests/test_strings.py::test_contains - AssertionError: assert 'pytest'...
2 failed, 3 passed in 0.01s
"""
        result = filter_output(
            "pytest -q",
            stdout,
            "",
            1,
            plan=plan_command("pytest -q"),
        )
        self.assertEqual(result.filter_name, "python.pytest")
        self.assertIn("Pytest: 2 failed, 3 passed in 0.01s", result.output)
        self.assertIn("[FAIL] test_divide_fail", result.output)
        self.assertIn("[FAIL] test_contains", result.output)
        self.assertNotIn("FAILED tests/test_math.py::test_divide_fail", result.output)

    def test_ruff_format_check_lists_files_needing_formatting(self):
        stdout = """Would reformat: src/app.py
Would reformat: tests/test_app.py
2 files would be reformatted, 3 files left unchanged
"""
        result = filter_output(
            "ruff format --check .",
            stdout,
            "",
            1,
            plan=plan_command("ruff format --check ."),
        )
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("Ruff format: 2 files need formatting", result.output)
        self.assertIn("src/app.py", result.output)
        self.assertIn("3 files already formatted", result.output)

    def test_ruff_format_write_summarizes_reformatted_files(self):
        stdout = "2 files reformatted, 3 files left unchanged\n"
        result = filter_output(
            "ruff format .",
            stdout,
            "",
            0,
            plan=plan_command("ruff format ."),
        )
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertEqual(
            result.output, "Ruff format: 2 files reformatted (3 unchanged)"
        )
