import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersGraphiteTests(unittest.TestCase):
    def test_gt_log_strips_emails_and_truncates_entries(self):
        stdout = """◉  abc1234 feat/add-auth 2d ago dev@example.com
│  feat(auth): add login endpoint
│
◉  def5678 feat/add-db 3d ago admin@example.com
│  feat(db): add migration system
~
"""
        result = filter_output("gt log", stdout, "", 0, plan=plan_command("gt log"))
        self.assertEqual(result.filter_name, "gt.log")
        self.assertIn("feat/add-auth", result.output)
        self.assertNotIn("@example.com", result.output)

    def test_gt_submit_summarizes_pushes_and_prs(self):
        stdout = """Pushed branch feat/add-auth
Created pull request #42 for feat/add-auth
Pushed branch feat/add-db
Updated pull request #40 for feat/add-db
"""
        result = filter_output(
            "gt submit", stdout, "", 0, plan=plan_command("gt submit")
        )
        self.assertEqual(result.filter_name, "gt.submit")
        self.assertIn("pushed feat/add-auth, feat/add-db", result.output)
        self.assertIn("created PR #42 feat/add-auth", result.output)

    def test_gt_sync_summarizes_deleted_branches(self):
        stdout = """Synced with remote
Deleted branch feat/merged-feature
Deleted branch fix/old-hotfix
"""
        result = filter_output("gt sync", stdout, "", 0, plan=plan_command("gt sync"))
        self.assertEqual(result.filter_name, "gt.sync")
        self.assertEqual(
            result.output,
            "ok sync: 1 synced, 2 deleted (feat/merged-feature, fix/old-hotfix)",
        )

    def test_gt_restack_summarizes_restacked_branches(self):
        stdout = """Restacked branch feat/add-auth on main
Restacked branch feat/add-db on feat/add-auth
Restacked branch fix/parsing on feat/add-db
"""
        result = filter_output(
            "gt restack", stdout, "", 0, plan=plan_command("gt restack")
        )
        self.assertEqual(result.filter_name, "gt.restack")
        self.assertEqual(result.output, "ok restacked 3 branches")

    def test_gt_create_summarizes_created_branch(self):
        result = filter_output(
            "gt create",
            "Created branch feat/new-feature\n",
            "",
            0,
            plan=plan_command("gt create"),
        )
        self.assertEqual(result.filter_name, "gt.create")
        self.assertEqual(result.output, "ok created feat/new-feature")

    def test_gt_branch_preserves_branch_output(self):
        stdout = """* feat/current
  feat/next
"""
        result = filter_output(
            "gt branch", stdout, "", 0, plan=plan_command("gt branch")
        )
        self.assertEqual(result.filter_name, "gt.branch")
        self.assertEqual(result.output, stdout.strip())
