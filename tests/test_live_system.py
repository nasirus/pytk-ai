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
        self.assertIn("3F 2D:", result.filtered_output)
        self.assertIn("src/ app.py util.py", result.filtered_output)
        self.assertIn("tests/ test_app.py", result.filtered_output)

    def test_diff_direct_file_compare(self):
        before = self.root / "before.txt"
        after = self.root / "after.txt"
        before.write_text("alpha\nbeta\n")
        after.write_text("alpha\ngamma\n")

        result = run_command("diff before.txt after.txt", cwd=str(self.root))
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIn("after.txt", result.filtered_output)
        self.assertIn("+1 added, -1 removed, ~0 modified", result.filtered_output)

    def test_wc(self):
        result = run_command("wc src/app.py", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn("src/app.py", result.filtered_output)

    def test_cat(self):
        result = run_command("cat src/app.py", cwd=str(self.root))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("def main():", result.filtered_output)

    def test_pytk_read_subcommand_executes(self):
        result = run_command(
            "pytk-ai read src/app.py --line-numbers", cwd=str(self.root)
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "read")
        self.assertIn("1 | def main():", result.filtered_output)

    def test_pytk_read_subcommand_minimal_filters_comments(self):
        file_path = self.root / "commented.py"
        file_path.write_text(
            '# private\n"""module docs"""\n\ndef main():\n    return 1\n'
        )

        result = run_command(
            "pytk-ai read commented.py --level minimal", cwd=str(self.root)
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "read")
        self.assertIn('"""module docs"""', result.filtered_output)
        self.assertIn("def main():", result.filtered_output)
        self.assertNotIn("# private", result.filtered_output)

    def test_pytk_read_subcommand_aggressive_elides_implementation(self):
        file_path = self.root / "module.rs"
        file_path.write_text(
            'use std::fmt;\n\nfn main() {\n    println!("hello");\n}\n\nconst LIMIT: usize = 5;\n'
        )

        result = run_command(
            "pytk-ai read module.rs --level aggressive", cwd=str(self.root)
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.filter_name, "read")
        self.assertIn("use std::fmt;", result.filtered_output)
        self.assertIn("fn main() {", result.filtered_output)
        self.assertIn("const LIMIT: usize = 5;", result.filtered_output)
        self.assertNotIn('println!("hello")', result.filtered_output)

    def test_cat_missing_file(self):
        result = run_command("cat no_such_file.txt", cwd=str(self.root))
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No such file or directory", result.filtered_output)
