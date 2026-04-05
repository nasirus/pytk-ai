"""Live execution tests for system/file commands against real directories."""

import tempfile
import unittest
from pathlib import Path

from pytk_ai.runner import run_command


class LiveSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ptk-live-sys-")
        cls.root = Path(cls._tmpdir.name)

        # Create a directory structure for ls/find/tree/wc
        src = cls.root / "src"
        src.mkdir()
        (src / "app.py").write_text("def main():\n    pass\n")
        (src / "util.py").write_text("x = 1\n")
        tests_dir = cls.root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_ls(self):
        result = run_command("ls", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("src", result.filtered_output)
        self.assertIn("tests", result.filtered_output)

    def test_find(self):
        result = run_command("find . -name '*.py'", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("app.py", result.filtered_output)

    def test_wc(self):
        result = run_command("wc src/app.py", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn("src/app.py", result.filtered_output)

    def test_cat(self):
        result = run_command("cat src/app.py", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("def main():", result.filtered_output)

    def test_cat_missing_file(self):
        result = run_command("cat no_such_file.txt", cwd=str(self.root))
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No such file or directory", result.filtered_output)
