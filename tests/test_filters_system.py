import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersSystemTests(unittest.TestCase):
    def test_tail_deduplicates_repeated_lines(self):
        stdout = "tick\nsame\nsame\nsame\nsame\nend\n"
        result = filter_output(
            "tail server.log", stdout, "", 0, plan=plan_command("tail server.log")
        )
        self.assertEqual(result.filter_name, "system.read.tail")
        self.assertIn("repeated line omitted 3 time(s)", result.output)

    def test_cat_failure_preserves_raw_error(self):
        stderr = "cat: missing.txt: No such file or directory\n"
        result = filter_output(
            "cat missing.txt", "", stderr, 1, plan=plan_command("cat missing.txt")
        )
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertIn("No such file or directory", result.output)

    def test_cat_filename_containing_tail_does_not_collapse_lines(self):
        stdout = "same\nsame\nsame\nsame\n"
        result = filter_output(
            "cat tailwind.config.js",
            stdout,
            "",
            0,
            plan=plan_command("cat tailwind.config.js"),
        )
        self.assertEqual(result.filter_name, "system.read.cat")
        self.assertEqual(result.output, "same\nsame\nsame\nsame")

    def test_tail_collapses_repeated_lines(self):
        stdout = "tick\nsame\nsame\nsame\nsame\nend\n"
        result = filter_output(
            "tail app.log", stdout, "", 0, plan=plan_command("tail app.log")
        )
        self.assertEqual(result.filter_name, "system.read.tail")
        self.assertIn("repeated line omitted 3 time(s)", result.output)

    def test_ls_la_compact_output(self):
        stdout = (
            "total 48\n"
            "drwxr-xr-x  15 user staff  480 Jan  1 12:00 .\n"
            "drwxr-xr-x   5 user staff  160 Jan  1 12:00 ..\n"
            "drwxr-xr-x  12 user staff  384 Jan  1 12:00 .git\n"
            "drwxr-xr-x   8 user staff  256 Jan  1 12:00 src\n"
            "-rw-r--r--   1 user staff 1234 Jan  1 12:00 Cargo.toml\n"
            "-rw-r--r--   1 user staff 5678 Jan  1 12:00 README.md\n"
        )
        result = filter_output("ls -la", stdout, "", 0, plan=plan_command("ls -la"))
        self.assertEqual(result.filter_name, "system.ls")
        self.assertIn("src/", result.output)
        self.assertIn("Cargo.toml  1.2K", result.output)
        self.assertIn("README.md  5.5K", result.output)
        self.assertNotIn(".git", result.output)
        self.assertNotIn("drwx", result.output)
        self.assertNotIn("total 48", result.output)

    def test_ls_la_filters_noise_dirs(self):
        stdout = (
            "total 16\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 node_modules\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 __pycache__\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 .venv\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 src\n"
            "-rw-r--r--  1 user staff 100 Jan  1 12:00 main.py\n"
        )
        result = filter_output("ls -la", stdout, "", 0, plan=plan_command("ls -la"))
        self.assertNotIn("node_modules", result.output)
        self.assertNotIn("__pycache__", result.output)
        self.assertNotIn(".venv", result.output)
        self.assertIn("src/", result.output)
        self.assertIn("main.py", result.output)

    def test_ls_la_show_all_preserves_noise(self):
        stdout = (
            "total 16\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 node_modules\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 src\n"
            "-rw-r--r--  1 user staff 100 Jan  1 12:00 main.py\n"
        )
        result = filter_output(
            "ls -la -a", stdout, "", 0, plan=plan_command("ls -la -a")
        )
        self.assertIn("node_modules/", result.output)
        self.assertIn("src/", result.output)

    def test_ls_summary_line(self):
        stdout = (
            "total 16\n"
            "drwxr-xr-x  3 user staff  96 Jan  1 12:00 src\n"
            "-rw-r--r--  1 user staff 100 Jan  1 12:00 main.py\n"
            "-rw-r--r--  1 user staff 200 Jan  1 12:00 utils.py\n"
        )
        result = filter_output("ls -la", stdout, "", 0, plan=plan_command("ls -la"))
        self.assertIn("2 files, 1 dir", result.output)
        self.assertIn(".py 2", result.output)

    def test_ls_symlinks_preserved(self):
        stdout = (
            "total 8\n"
            "lrwxr-xr-x  1 user staff 12 Jan  1 12:00 link -> target\n"
            "-rw-r--r--  1 user staff 100 Jan  1 12:00 file.txt\n"
        )
        result = filter_output("ls -la", stdout, "", 0, plan=plan_command("ls -la"))
        self.assertIn("link -> target", result.output)
        self.assertIn("1 symlink", result.output)
