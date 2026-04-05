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
