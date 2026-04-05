import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersGitTests(unittest.TestCase):
    def test_git_status_porcelain_uses_dense_symbolic_output(self):
        stdout = """## No commits yet on master
?? .gitignore
?? .python-version
?? README.md
?? main.py
?? pyproject.toml
?? uv.lock
"""
        result = filter_output(
            "git status",
            stdout,
            "",
            0,
            plan=plan_command("git status"),
        )
        self.assertEqual(result.filter_name, "git.status")
        self.assertEqual(
            result.output,
            "master (no commits)\n? .gitignore .python-version README.md main.py pyproject.toml uv.lock",
        )

    def test_git_status_groups_paths_by_directory_symbolically(self):
        stdout = """## main
 M README.md
 M TODO.md
 M src/pytk_ai/filters/git.py
 M src/pytk_ai/filters/system.py
 M src/pytk_ai/plan/planner.py
 M tests/test_filters_git.py
 M tests/test_live_git.py
 M tests/test_plan_execution_rewrites.py
 M tests/test_plan_planner.py
?? src/pytk_ai/plan/execution_rewrites.py
?? tests/test_plan_execution_rewrites.py
"""
        result = filter_output(
            "git status",
            stdout,
            "",
            0,
            plan=plan_command("git status"),
            max_output_lines=20,
        )
        self.assertEqual(
            result.output,
            "main\nM README.md TODO.md src/pytk_ai/filters/{git.py,system.py} src/pytk_ai/plan/planner.py tests/{test_filters_git.py,test_live_git.py,test_plan_execution_rewrites.py,test_plan_planner.py}\n? src/pytk_ai/plan/execution_rewrites.py tests/test_plan_execution_rewrites.py",
        )

    def test_git_status_never_returns_longer_text_than_raw_porcelain(self):
        stdout = """## main
 M a/very/deeply/nested/path/with/a/long_filename_that_repeats.py
"""
        result = filter_output(
            "git status",
            stdout,
            "",
            0,
            plan=plan_command("git status"),
        )
        self.assertLessEqual(len(result.output), len(stdout.strip()))

    def test_git_status_human_output_falls_back_without_porcelain_parse(self):
        stdout = """On branch master

No commits yet

Untracked files:
	README.md

nothing added to commit but untracked files present
"""
        result = filter_output(
            "git status",
            stdout,
            "",
            0,
            plan=plan_command("git status"),
        )
        self.assertIn("On branch master", result.output)
        self.assertIn("Untracked files:", result.output)

    def test_git_log_reduces_full_commit_blocks_to_one_line(self):
        stdout = """commit abc1234567890 (HEAD -> main)
Author: Test User <test@example.com>
Date:   Sun Apr 5 12:00:00 2026 +0000

    Add planner coverage

commit def4567890abcd
Author: Test User <test@example.com>
Date:   Sat Apr 4 12:00:00 2026 +0000

    Fix filter fallback
"""
        result = filter_output(
            "git log -2", stdout, "", 0, plan=plan_command("git log -2")
        )
        self.assertEqual(result.filter_name, "git.log")
        self.assertIn("abc1234 HEAD -> main Add planner coverage", result.output)
        self.assertIn("def4567 Fix filter fallback", result.output)
        self.assertNotIn("Author:", result.output)

    def test_git_diff_compacts_patch_to_per_file_summary(self):
        stdout = """diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
-old = 1
+new = 2
 unchanged = True
+extra = 3
"""
        result = filter_output("git diff", stdout, "", 0, plan=plan_command("git diff"))
        self.assertEqual(result.filter_name, "git.diff")
        self.assertIn("src/app.py (+2/-1)", result.output)
        self.assertIn("+ new = 2", result.output)
        self.assertNotIn("@@", result.output)

    def test_git_commit_success_is_reduced_to_hash_and_subject(self):
        stdout = "[main abc1234] Add compact git commit filter\n 2 files changed, 5 insertions(+)\n"
        result = filter_output(
            'git commit -m "Add compact git commit filter"',
            stdout,
            "",
            0,
            plan=plan_command('git commit -m "Add compact git commit filter"'),
        )
        self.assertEqual(result.output, "ok abc1234 Add compact git commit filter")

    def test_git_pull_success_keeps_only_change_totals(self):
        stdout = """Updating abc1234..def5678
Fast-forward
 src/app.py | 8 ++++++--
 1 file changed, 6 insertions(+), 2 deletions(-)
"""
        result = filter_output("git pull", stdout, "", 0, plan=plan_command("git pull"))
        self.assertEqual(result.output, "ok 1 files +6 -2")

    def test_git_branch_vv_preserves_non_current_branches(self):
        stdout = """  feature/login 1234567 [origin/feature/login] Add login flow
* main          89abcde [origin/main] Ship phase 1
  release/1.0   fedcba9 [origin/release/1.0: gone] Prepare release
"""
        result = filter_output(
            "git branch -vv",
            stdout,
            "",
            0,
            plan=plan_command("git branch -vv"),
        )
        self.assertEqual(result.filter_name, "git.branch")
        self.assertIn("feature/login 1234567", result.output)
        self.assertIn("* main          89abcde", result.output)
        self.assertIn("release/1.0   fedcba9", result.output)

    def test_git_add_preserves_success_warnings(self):
        stderr = (
            "warning: adding embedded git repository: vendor/lib\n"
            "hint: You've added another git repository inside your current repository.\n"
        )
        result = filter_output(
            "git add vendor/lib",
            "",
            stderr,
            0,
            plan=plan_command("git add vendor/lib"),
        )
        self.assertEqual(result.filter_name, "git.add")
        self.assertIn("warning: adding embedded git repository", result.output)

    def test_git_failure_preserves_actionable_output(self):
        stderr = "fatal: ambiguous argument 'missing': unknown revision or path not in the working tree.\n"
        result = filter_output(
            "git show missing",
            "",
            stderr,
            128,
            plan=plan_command("git show missing"),
        )
        self.assertEqual(result.filter_name, "git.show")
        self.assertIn("fatal:", result.output)
