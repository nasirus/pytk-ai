import unittest

from pytk_ai.filters import filter_output
from pytk_ai.filters.files import render_read_output, smart_truncate_read
from pytk_ai.plan import plan_command


class FiltersFilesTests(unittest.TestCase):
    def test_render_read_output_minimal_strips_comments(self):
        content = '// comment\nfn main() {\n    println!("hi");\n}\n'
        result = render_read_output(content, source_path="main.rs", level="minimal")
        self.assertNotIn("// comment", result)
        self.assertIn("fn main()", result)

    def test_render_read_output_minimal_keeps_doc_comments(self):
        content = (
            '/// public docs\n// private note\nfn main() {\n    println!("hi");\n}\n'
        )
        result = render_read_output(content, source_path="main.rs", level="minimal")
        self.assertIn("/// public docs", result)
        self.assertNotIn("// private note", result)

    def test_render_read_output_aggressive_keeps_structure(self):
        content = "\n".join(
            [
                "use std::fmt;",
                "",
                "fn main() {",
                '    println!("hi");',
                "}",
                "",
                "const LIMIT: usize = 5;",
            ]
        )
        result = render_read_output(content, source_path="main.rs", level="aggressive")
        self.assertIn("use std::fmt;", result)
        self.assertIn("fn main() {", result)
        self.assertIn("const LIMIT: usize = 5;", result)
        self.assertNotIn('println!("hi")', result)

    def test_render_read_output_with_line_numbers(self):
        content = "alpha\nbeta\n"
        result = render_read_output(
            content,
            source_path="notes.txt",
            level="none",
            line_numbers=True,
        )
        self.assertEqual(result, "1 | alpha\n2 | beta")

    def test_render_read_output_tail_lines(self):
        content = "a\nb\nc\nd\n"
        result = render_read_output(
            content,
            source_path="notes.txt",
            level="none",
            tail_lines=2,
        )
        self.assertEqual(result, "c\nd\n")

    def test_smart_truncate_read_prefers_structural_lines(self):
        content = "\n".join(
            [
                "import os",
                "import sys",
                "",
                "def alpha():",
                "    first = 1",
                "    second = 2",
                "    third = 3",
                "",
                "def beta():",
                "    fourth = 4",
                "    fifth = 5",
                "",
                "export const value = 1",
            ]
        )
        result = smart_truncate_read(content, 6, "python")
        self.assertIn("import os", result)
        self.assertIn("def alpha():", result)
        self.assertIn("def beta():", result)
        self.assertIn("# ...", result)

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

    def test_compound_grep_uses_managed_segment_command(self):
        command = "cd /workspace/project && grep -n 'def ' src/app.py"
        stdout = """src/app.py:10:def main():
src/app.py:14:    return main()
"""
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("2 matches in 1 files", result.output)
        self.assertIn("src/app.py (2)", result.output)

    def test_plain_grep_still_uses_search_filter_name(self):
        stdout = """src/app.py:10:def main():
src/app.py:14:    return main()
"""
        result = filter_output(
            "grep -n 'def ' src/app.py",
            stdout,
            "",
            0,
            plan=plan_command("grep -n 'def ' src/app.py"),
        )
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("2 matches in 1 files", result.output)

    def test_plain_grep_with_trailing_semicolon_keeps_search_filter_name(self):
        stdout = """src/app.py:10:def main():
src/app.py:14:    return main()
"""
        command = "grep -n 'def ' src/app.py;"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("2 matches in 1 files", result.output)

    def test_grep_with_true_guard_keeps_search_filter_name(self):
        stdout = """src/app.py:10:def main():
src/app.py:14:    return main()
"""
        command = "grep -n 'def ' src/app.py || true"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertIn("2 matches in 1 files", result.output)

    def test_grep_no_matches_with_true_guard_reports_zero_matches(self):
        command = "grep -n 'def ' src/app.py || true"
        result = filter_output(command, "", "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.grep")
        self.assertEqual(result.output, "0 matches")

    def test_grep_with_redirected_error_and_true_guard_falls_back_to_generic(self):
        command = "grep foo missing.txt 2>/dev/null || true"
        result = filter_output(command, "", "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "")

    def test_relative_cd_prefix_with_stdout_falls_back_to_generic(self):
        command = "cd repo && grep -n 'def ' src/app.py"
        stdout = "/workspace/project\nsrc/app.py:10:def main()\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "/workspace/project\nsrc/app.py:10:def main()")

    def test_grep_with_non_noop_or_tail_falls_back_to_generic(self):
        command = "grep -n 'def ' src/app.py || echo nope"
        stdout = "src/app.py:10:def main()\nnope\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "src/app.py:10:def main()\nnope")

    def test_compound_grep_with_trailing_command_falls_back_to_generic(self):
        command = "cd /workspace/project && grep -n 'def ' src/app.py && echo done"
        stdout = "src/app.py:10:def main()\ndone\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "src/app.py:10:def main()\ndone")

    def test_piped_grep_falls_back_to_generic(self):
        command = "grep -n 'def ' src/app.py | head -n 1"
        stdout = "src/app.py:10:def main()\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "src/app.py:10:def main()")

    def test_semicolon_cd_prefix_falls_back_to_generic(self):
        command = "cd /missing; grep -n 'def ' src/app.py"
        stdout = "src/app.py:10:def main()\n"
        stderr = "bash: line 1: cd: /missing: No such file or directory\n"
        result = filter_output(command, stdout, stderr, 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("cd: /missing", result.output)
        self.assertIn("src/app.py:10:def main()", result.output)

    def test_failed_cd_and_grep_falls_back_to_generic(self):
        command = "cd /missing && grep -n 'def ' src/app.py"
        stderr = "bash: line 1: cd: /missing: No such file or directory\n"
        result = filter_output(command, "", stderr, 1, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("cd: /missing", result.output)

    def test_cd_dash_prefix_falls_back_to_generic(self):
        command = "cd - && grep -n 'def ' src/app.py"
        stdout = "/workspace/previous\nsrc/app.py:10:def main()\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "/workspace/previous\nsrc/app.py:10:def main()")

    def test_cd_with_redirect_prefix_falls_back_to_generic(self):
        command = "cd /missing 2>/dev/null && grep -n 'def ' src/app.py"
        result = filter_output(command, "", "", 1, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "")

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
        self.assertIn("4F 4D:", result.output)
        self.assertIn("src/ app.py", result.output)
        self.assertIn("src/lib/ util.py", result.output)
        self.assertIn("./ README.md", result.output)
        self.assertIn("ext: .py(3) .md(1)", result.output)

    def test_compound_find_uses_managed_segment_command(self):
        command = "cd /workspace/project && find . -name '*.py'"
        stdout = """src/app.py
src/lib/util.py
tests/test_app.py
README.md
"""
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("4F 4D:", result.output)
        self.assertIn("src/ app.py", result.output)

    def test_compound_find_with_trailing_semicolon_keeps_search_filter_name(self):
        command = "cd /workspace/project && find . -name '*.py';"
        stdout = """src/app.py
src/lib/util.py
tests/test_app.py
README.md
"""
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("4F 4D:", result.output)
        self.assertIn("src/ app.py", result.output)

    def test_compound_find_with_true_guard_falls_back_to_generic(self):
        command = "cd /workspace/project && find missingdir -name '*.py' || true"
        stderr = "find: 'missingdir': No such file or directory\n"
        result = filter_output(command, "", stderr, 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("find: 'missingdir': No such file or directory", result.output)

    def test_find_with_true_guard_keeps_search_filter_name(self):
        command = "find . -name '*.py' || true"
        stdout = "src/app.py\ntests/test_app.py\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "search.find")
        self.assertIn("2F 2D:", result.output)
        self.assertIn("src/ app.py", result.output)

    def test_find_with_redirected_error_and_true_guard_falls_back_to_generic(self):
        command = "find missingdir 2>/dev/null || true"
        result = filter_output(command, "", "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "")

    def test_compound_find_with_trailing_command_falls_back_to_generic(self):
        command = "cd /workspace/project && find . -name '*.py' && echo done"
        stdout = "src/app.py\ntests/test_app.py\ndone\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertEqual(result.output, "src/app.py\ntests/test_app.py\ndone")

    def test_failed_cd_and_find_falls_back_to_generic(self):
        command = "cd /missing && find . -name '*.py'"
        stderr = "bash: line 1: cd: /missing: No such file or directory\n"
        result = filter_output(command, "", stderr, 1, plan=plan_command(command))
        self.assertEqual(result.filter_name, "generic")
        self.assertIn("cd: /missing", result.output)

    def test_pytk_read_with_true_guard_preserves_read_window(self):
        command = "pytk-ai read demo.py --tail-lines 1 || true"
        stdout = "a\nb\nc\n"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "read")
        self.assertEqual(result.output, "c")

    def test_tree_extracts_summary_and_keeps_shape(self):
        stdout = """.\n├── src\n│   ├── app.py\n│   └── lib.py\n└── tests\n    └── test_app.py\n\n2 directories, 3 files\n"""
        result = filter_output("tree", stdout, "", 0, plan=plan_command("tree"))
        self.assertEqual(result.filter_name, "files.tree")
        self.assertIn("2 directories, 3 files", result.output)
        self.assertIn("├── src", result.output)
        self.assertNotIn("\n.\n", f"\n{result.output}\n")

    def test_tree_with_true_guard_keeps_tree_filter_name(self):
        stdout = """.\n├── src\n└── tests\n\n2 directories, 0 files\n"""
        command = "tree || true"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "files.tree")
        self.assertIn("2 directories, 0 files", result.output)

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

    def test_wc_with_true_guard_keeps_wc_filter_name(self):
        stdout = "  10 demo.py\n"
        command = "wc -l demo.py || true"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "files.wc")
        self.assertEqual(result.output, "wc demo.py: 10 lines")

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

    def test_diff_direct_file_compare_uses_rtk_style_header(self):
        stdout = """--- a.txt	2026-04-05 00:00:00.000000000 +0000
+++ b.txt	2026-04-05 00:00:00.000000000 +0000
@@ -1,2 +1,2 @@
-old value
+new value
 keep
"""
        result = filter_output(
            "diff a.txt b.txt",
            stdout,
            "",
            1,
            plan=plan_command("diff a.txt b.txt"),
        )
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIn("b.txt", result.output)
        self.assertIn("+1 added, -1 removed, ~0 modified", result.output)
        self.assertIn("+ new value", result.output)

    def test_diff_direct_file_compare_identical_files(self):
        result = filter_output(
            "diff a.txt b.txt",
            "",
            "",
            0,
            plan=plan_command("diff a.txt b.txt"),
        )
        self.assertEqual(result.filter_name, "files.diff")
        self.assertEqual(result.output, "[ok] Files are identical")

    def test_diff_with_true_guard_keeps_diff_filter_name(self):
        stdout = """--- a.txt
+++ b.txt
@@ -1 +1 @@
-old
+new
"""
        command = "diff -u a.txt b.txt || true"
        result = filter_output(command, stdout, "", 0, plan=plan_command(command))
        self.assertEqual(result.filter_name, "files.diff")
        self.assertIn("b.txt (+1/-1)", result.output)

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

    def test_pytk_read_filter_uses_requested_level_and_line_numbers(self):
        stdout = "# comment\ndef main():\n    return 1\n"
        result = filter_output(
            "pytk-ai read demo.py --level minimal --line-numbers",
            stdout,
            "",
            0,
            plan=plan_command("pytk-ai read demo.py --level minimal --line-numbers"),
        )
        self.assertEqual(result.filter_name, "read")
        self.assertEqual(result.output, "1 | def main():\n2 |     return 1")

    def test_pytk_read_filter_uses_structural_max_lines(self):
        stdout = "\n".join(
            [
                "import os",
                "import sys",
                "",
                "def alpha():",
                "    a = 1",
                "    b = 2",
                "    c = 3",
                "",
                "def beta():",
                "    d = 4",
                "    e = 5",
            ]
        )
        result = filter_output(
            "pytk-ai read demo.py --max-lines 5",
            stdout,
            "",
            0,
            plan=plan_command("pytk-ai read demo.py --max-lines 5"),
        )
        self.assertEqual(result.filter_name, "read")
        self.assertIn("def beta():", result.output)
        self.assertIn("# ...", result.output)
