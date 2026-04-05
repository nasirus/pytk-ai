import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersFilesTests(unittest.TestCase):
    def test_rg_groups_matches_by_file(self):
        stdout = """src/app.py:10:def main():
src/app.py:14:    return main()
tests/test_app.py:3:from src.app import main
"""
        result = filter_output("rg main", stdout, "", 0, plan=plan_command("rg main"))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("3 matches in 2 files", result.output)
        self.assertIn("src/app.py (2)", result.output)
        self.assertIn("10: def main()", result.output)

    def test_rg_failure_keeps_raw_stderr(self):
        stderr = "regex parse error:\n    [\n    ^\nerror: unclosed character class\n"
        result = filter_output("rg [ src", "", stderr, 2, plan=plan_command("rg [ src"))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("regex parse error", result.output)
        self.assertIn("unclosed character class", result.output)

    def test_find_groups_paths_by_directory(self):
        stdout = """src/app.py
src/lib/util.py
tests/test_app.py
README.md
"""
        result = filter_output(
            "find . -name '*.py'",
            stdout,
            "",
            0,
            plan=plan_command("find . -name '*.py'"),
        )
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("4 paths in 4 directories", result.output)
        self.assertIn("src (1)", result.output)
        self.assertIn("src/lib (1)", result.output)
        self.assertIn("README.md", result.output)

    def test_tree_extracts_summary_and_keeps_shape(self):
        stdout = """.\n├── src\n│   ├── app.py\n│   └── lib.py\n└── tests\n    └── test_app.py\n\n2 directories, 3 files\n"""
        result = filter_output("tree", stdout, "", 0, plan=plan_command("tree"))
        self.assertEqual(result.filter_name, "files.tree")
        self.assertIn("2 directories, 3 files", result.output)
        self.assertIn("├── src", result.output)
        self.assertNotIn("\n.\n", f"\n{result.output}\n")

    def test_wc_summarizes_totals_and_files(self):
        stdout = """  10  30 200 src/app.py
   5  12  80 tests/test_app.py
  15  42 280 total
"""
        result = filter_output(
            "wc src/app.py tests/test_app.py",
            stdout,
            "",
            0,
            plan=plan_command("wc src/app.py tests/test_app.py"),
        )
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn(
            "wc total: 15 lines, 42 words, 280 bytes across 2 files", result.output
        )
        self.assertIn("src/app.py: 10 lines, 30 words, 200 bytes", result.output)

    def test_wc_two_column_output_uses_flags_not_column_count(self):
        stdout = "  10  30 src/app.py\n"
        result = filter_output(
            "wc -lw src/app.py",
            stdout,
            "",
            0,
            plan=plan_command("wc -lw src/app.py"),
        )
        self.assertEqual(result.filter_name, "files.wc")
        self.assertIn("wc src/app.py: 10 lines, 30 words", result.output)
        self.assertNotIn("bytes", result.output)

    def test_wc_unknown_option_falls_back_to_raw_output(self):
        stdout = "  10  30 src/app.py\n"
        result = filter_output(
            "wc --total=always src/app.py",
            stdout,
            "",
            0,
            plan=plan_command("wc --total=always src/app.py"),
        )
        self.assertEqual(result.filter_name, "files.wc")
        self.assertEqual(result.output, "10  30 src/app.py")

    def test_diff_summarizes_unified_patch(self):
        stdout = """--- a.txt
+++ b.txt
@@ -1,2 +1,3 @@
-old
+new
 keep
+extra
"""
        result = filter_output(
            "diff -u a.txt b.txt",
            stdout,
            "",
            1,
            plan=plan_command("diff -u a.txt b.txt"),
        )
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIn("b.txt (+2/-1)", result.output)
        self.assertIn("+ new", result.output)
        self.assertIn("+ extra", result.output)

    def test_env_prefixed_and_absolute_commands_use_file_filters(self):
        grep_result = filter_output(
            "env BAR=1 rg main src",
            "src/app.py:10:def main()\n",
            "",
            0,
            plan=plan_command("env BAR=1 rg main src"),
        )
        self.assertEqual(grep_result.filter_name, "search.grep")
        self.assertIn("1 matches in 1 files", grep_result.output)

        diff_result = filter_output(
            "/usr/bin/diff -u a.txt b.txt",
            "--- a.txt\n+++ b.txt\n@@ -1 +1 @@\n-old\n+new\n",
            "",
            1,
            plan=plan_command("/usr/bin/diff -u a.txt b.txt"),
        )
        self.assertEqual(diff_result.filter_name, "files.diff")
        self.assertIn("b.txt (+1/-1)", diff_result.output)
