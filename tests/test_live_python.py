"""Live execution tests for Python tool commands (ruff, mypy)."""

import tempfile
import unittest
from pathlib import Path

try:
    from tests.helpers import requires_tool
except ImportError:
    from helpers import requires_tool
from pytk_ai.runner import run_command


@requires_tool("ruff")
class LiveRuffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ptk-live-py-")
        cls.root = Path(cls._tmpdir.name)

        # Write a .py file with known lint issues
        (cls.root / "bad.py").write_text("import os\nimport sys\n\nx = 1\n")

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_ruff_check_finds_unused_imports(self):
        result = run_command("ruff check bad.py", cwd=str(self.root))
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "python.ruff")
        self.assertIn("F401", result.filtered_output)
        self.assertIn("bad.py", result.filtered_output)

    def test_ruff_format_check_on_clean_file(self):
        clean = self.root / "clean.py"
        clean.write_text('x = 1\ny = "hello"\n')
        result = run_command("ruff format --check clean.py", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)


@requires_tool("mypy")
class LiveMypyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ptk-live-mypy-")
        cls.root = Path(cls._tmpdir.name)

        (cls.root / "typed.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n\nadd(1, 'x')\n"
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_mypy_detects_type_error(self):
        result = run_command("mypy typed.py", cwd=str(self.root))
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "python.mypy")
        self.assertIn("typed.py", result.filtered_output)
