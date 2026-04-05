import unittest

from pytk_ai.plan import plan_command


class PlanPlannerTests(unittest.TestCase):
    def test_plan_command_rewrites_supported_command_and_sets_filter_hint(self):
        plan = plan_command("git status")
        self.assertTrue(plan.managed)
        self.assertTrue(plan.changed)
        self.assertEqual(plan.planned_command, "pytk-ai git status")
        self.assertEqual(plan.execution_command, "git status --porcelain=v1 --branch")
        self.assertEqual(plan.filter_hint, "git")

    def test_plan_command_rewrites_env_prefixed_git_status_execution(self):
        plan = plan_command("FOO=1 git status > out.txt 2>&1")
        self.assertEqual(
            plan.planned_command, "FOO=1 pytk-ai git status > out.txt 2>&1"
        )
        self.assertEqual(
            plan.execution_command,
            "FOO=1 git status --porcelain=v1 --branch > out.txt 2>&1",
        )

    def test_plan_command_preserves_compound_commands(self):
        plan = plan_command("git add . && cargo test")
        self.assertEqual(plan.planned_command, "pytk-ai git add . && pytk-ai test")
        self.assertEqual(len(plan.segments), 2)
        self.assertTrue(all(segment.managed for segment in plan.segments))

    def test_plan_command_rewrites_cargo_test_to_test_filter_hint(self):
        plan = plan_command("cargo test --lib")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai test --lib")
        self.assertEqual(plan.filter_hint, "test")

    def test_plan_command_keeps_unsupported_segments_raw(self):
        plan = plan_command("git status && htop")
        self.assertEqual(plan.planned_command, "pytk-ai git status && htop")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.segments[1].skip_reason, "unsupported-command")

    def test_plan_command_respects_excluded_commands(self):
        plan = plan_command("git status", excluded=("git",))
        self.assertFalse(plan.managed)
        self.assertEqual(plan.planned_command, "git status")
        self.assertEqual(plan.skip_reason, "excluded-command")

    def test_plan_command_rejects_disabled_prefix(self):
        plan = plan_command("PYTK_AI_DISABLED=1 git status")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "disabled")

    def test_plan_command_preserves_pipe_right_side(self):
        plan = plan_command("git log | head")
        self.assertEqual(plan.planned_command, "pytk-ai git log | head")
        self.assertTrue(plan.managed)

    def test_plan_command_skips_unsupported_pipe_source(self):
        plan = plan_command("find . | head")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "unsupported-pipe-source")

    def test_plan_command_returns_skip_reason_for_empty_command(self):
        plan = plan_command("  ")
        self.assertEqual(plan.skip_reason, "empty-command")
        self.assertEqual(plan.execution_command, "")

    def test_plan_command_rewrites_generic_test_wrappers(self):
        plan = plan_command("npm test")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai test")
        self.assertEqual(plan.filter_hint, "test")

    def test_plan_command_handles_file_commands(self):
        plan = plan_command("wc -l src/app.py")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai wc -l src/app.py")
        self.assertEqual(plan.filter_hint, "wc")

    def test_plan_command_rewrites_phase4_package_commands(self):
        plan = plan_command("uv sync")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("npm list --depth=0")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package --depth=0")
        self.assertEqual(plan.filter_hint, "package")

    def test_plan_command_rewrites_phase5_infra_commands(self):
        plan = plan_command("docker ps")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai docker ps")
        self.assertEqual(plan.filter_hint, "docker")

        plan = plan_command("kubectl get pods -A")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai kubectl get pods -A")
        self.assertEqual(plan.filter_hint, "kubectl")

        plan = plan_command("aws ec2 describe-instances --output table")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.planned_command,
            "pytk-ai aws ec2 describe-instances --output table",
        )
        self.assertEqual(plan.filter_hint, "aws")

        plan = plan_command("terraform validate -json")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai terraform validate -json")
        self.assertEqual(plan.filter_hint, "terraform")

    def test_plan_command_rewrites_phase6_github_and_api_commands(self):
        plan = plan_command("gh pr list")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh pr list")
        self.assertEqual(plan.filter_hint, "gh")

        plan = plan_command("gh pr view 42")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh pr view 42")
        self.assertEqual(plan.filter_hint, "gh")

        plan = plan_command("curl https://api.example.com/users")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.planned_command, "pytk-ai curl https://api.example.com/users"
        )
        self.assertEqual(plan.filter_hint, "curl")

        plan = plan_command("wget https://example.com/file.tar.gz")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.planned_command,
            "pytk-ai wget https://example.com/file.tar.gz",
        )
        self.assertEqual(plan.filter_hint, "wget")

    def test_plan_command_keeps_structured_gh_output_raw(self):
        plan = plan_command("gh pr view 42 --json number,title")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "gh-structured-output")
