import unittest

from ptk.plan import plan_command


class PlanPlannerTests(unittest.TestCase):
    def test_plan_command_rewrites_supported_command_and_sets_filter_hint(self):
        plan = plan_command("git status")
        self.assertTrue(plan.managed)
        self.assertTrue(plan.changed)
        self.assertEqual(plan.planned_command, "ptk git status")
        self.assertEqual(plan.execution_command, "git status")
        self.assertEqual(plan.filter_hint, "git")

    def test_plan_command_preserves_compound_commands(self):
        plan = plan_command("git add . && cargo test")
        self.assertEqual(plan.planned_command, "ptk git add . && ptk cargo test")
        self.assertEqual(len(plan.segments), 2)
        self.assertTrue(all(segment.managed for segment in plan.segments))

    def test_plan_command_keeps_unsupported_segments_raw(self):
        plan = plan_command("git status && htop")
        self.assertEqual(plan.planned_command, "ptk git status && htop")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.segments[1].skip_reason, "unsupported-command")

    def test_plan_command_respects_excluded_commands(self):
        plan = plan_command("git status", excluded=("git",))
        self.assertFalse(plan.managed)
        self.assertEqual(plan.planned_command, "git status")
        self.assertEqual(plan.skip_reason, "excluded-command")

    def test_plan_command_rejects_disabled_prefix(self):
        plan = plan_command("PTK_DISABLED=1 git status")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "disabled")

    def test_plan_command_preserves_pipe_right_side(self):
        plan = plan_command("git log | head")
        self.assertEqual(plan.planned_command, "ptk git log | head")
        self.assertTrue(plan.managed)

    def test_plan_command_skips_unsupported_pipe_source(self):
        plan = plan_command("find . | head")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "unsupported-pipe-source")

    def test_plan_command_returns_skip_reason_for_empty_command(self):
        plan = plan_command("  ")
        self.assertEqual(plan.skip_reason, "empty-command")
        self.assertEqual(plan.execution_command, "")
