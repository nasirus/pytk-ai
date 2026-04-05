import unittest

from pytk_ai.plan.normalize import (
    has_disabled_prefix,
    infer_filter_hint,
    normalize_absolute_first_token,
    rewrite_line_range,
    strip_env_prefix,
    strip_trailing_redirect_suffix,
)


class PlanNormalizeTests(unittest.TestCase):
    def test_strip_env_prefix_keeps_prefix_and_command(self):
        prefix, command = strip_env_prefix('FOO=1 BAR="two words" git status')
        self.assertEqual(prefix, 'FOO=1 BAR="two words" ')
        self.assertEqual(command, "git status")

    def test_normalize_absolute_first_token_uses_basename(self):
        self.assertEqual(
            normalize_absolute_first_token("/usr/bin/git status"),
            "git status",
        )

    def test_strip_trailing_redirect_suffix_preserves_suffix(self):
        command, suffix = strip_trailing_redirect_suffix("git status > out.txt 2>&1")
        self.assertEqual(command, "git status")
        self.assertEqual(suffix, " > out.txt 2>&1")

    def test_rewrite_line_range_handles_head_and_tail(self):
        self.assertEqual(
            rewrite_line_range("head -5 README.md"),
            "pytk-ai read README.md --max-lines 5",
        )
        self.assertEqual(
            rewrite_line_range("tail --lines 7 README.md"),
            "pytk-ai read README.md --tail-lines 7",
        )

    def test_has_disabled_prefix_detects_pytk_ai_and_rtk_flags(self):
        self.assertTrue(has_disabled_prefix("PYTK_AI_DISABLED=1 git status"))
        self.assertTrue(has_disabled_prefix("RTK_DISABLED=1 git status"))

    def test_infer_filter_hint_handles_pytk_ai_and_python_forms(self):
        self.assertEqual(infer_filter_hint("pytk-ai git status"), "git")
        self.assertEqual(infer_filter_hint("python -m pytest -q"), "pytest")

    def test_infer_filter_hint_handles_build_and_lint_commands(self):
        self.assertEqual(infer_filter_hint("cargo build"), "cargo")
        self.assertEqual(infer_filter_hint("eslint src"), "lint")
        self.assertEqual(infer_filter_hint("next build"), "next")
        self.assertEqual(infer_filter_hint("go test ./..."), "go")
        self.assertEqual(infer_filter_hint("bundle exec rspec"), "rspec")
        self.assertIsNone(infer_filter_hint("go version"))

    def test_infer_filter_hint_handles_file_commands(self):
        self.assertEqual(infer_filter_hint("tree -L 2"), "tree")
        self.assertEqual(infer_filter_hint("wc -l src/app.py"), "wc")
        self.assertEqual(infer_filter_hint("diff -u a b"), "diff")

    def test_infer_filter_hint_handles_package_manager_commands(self):
        self.assertEqual(infer_filter_hint("pip list"), "package")
        self.assertEqual(infer_filter_hint("uv pip list --outdated"), "package")
        self.assertEqual(infer_filter_hint("uv sync"), "package")
        self.assertEqual(infer_filter_hint("npm list"), "package")
        self.assertEqual(infer_filter_hint("pnpm ls"), "package")
        self.assertEqual(infer_filter_hint("bundle install"), "package")
        self.assertEqual(infer_filter_hint("npx prisma generate"), "package")

    def test_infer_filter_hint_handles_phase5_infra_commands(self):
        self.assertEqual(infer_filter_hint("docker ps"), "docker")
        self.assertEqual(infer_filter_hint("docker compose ps"), "docker")
        self.assertEqual(infer_filter_hint("kubectl get pods -A"), "kubectl")
        self.assertEqual(infer_filter_hint("aws ec2 describe-instances"), "aws")
        self.assertEqual(infer_filter_hint("terraform validate"), "terraform")
        self.assertIsNone(infer_filter_hint("docker compose up -d"))

    def test_infer_filter_hint_handles_phase6_github_and_api_commands(self):
        self.assertEqual(infer_filter_hint("gh pr list"), "gh")
        self.assertEqual(infer_filter_hint("gh pr view 42"), "gh")
        self.assertEqual(infer_filter_hint("gh issue list"), "gh")
        self.assertEqual(infer_filter_hint("gh run list"), "gh")
        self.assertEqual(infer_filter_hint("curl https://api.example.com"), "curl")
        self.assertEqual(
            infer_filter_hint("wget https://example.com/file.tar.gz"), "wget"
        )
        self.assertIsNone(infer_filter_hint("gh issue view 42"))
