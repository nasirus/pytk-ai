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

    def test_plan_command_rewrites_cargo_nextest_to_cargo_filter(self):
        plan = plan_command("cargo nextest run")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai cargo nextest run")
        self.assertEqual(plan.filter_hint, "cargo")

    def test_plan_command_keeps_unsupported_segments_raw(self):
        plan = plan_command("git status && htop")
        self.assertEqual(plan.planned_command, "pytk-ai git status && htop")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.segments[1].skip_reason, "unsupported-command")

    def test_plan_command_prefers_managed_filter_hint_in_compound_commands(self):
        plan = plan_command("cd /workspace/project && git status")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.filter_hint, "git")
        self.assertEqual(plan.segments[0].filter_hint, "cd")
        self.assertEqual(plan.segments[1].filter_hint, "git")

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

        plan = plan_command("playwright test --grep auth")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai playwright test --grep auth")
        self.assertEqual(plan.filter_hint, "playwright")

        plan = plan_command("pnpm vitest run src/auth.test.ts")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai vitest run src/auth.test.ts")
        self.assertEqual(plan.filter_hint, "vitest")

        plan = plan_command("rails test test/models/user_test.rb")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.planned_command, "pytk-ai rake test test/models/user_test.rb"
        )
        self.assertEqual(plan.filter_hint, "rake")

    def test_plan_command_handles_file_commands(self):
        plan = plan_command("wc -l src/app.py")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai wc -l src/app.py")
        self.assertEqual(plan.filter_hint, "wc")

        plan = plan_command("diff a.txt b.txt")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai diff a.txt b.txt")
        self.assertEqual(plan.execution_command, "diff -u a.txt b.txt")
        self.assertEqual(plan.filter_hint, "diff")

        plan = plan_command("find . -name '*.py'")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai find . -name '*.py'")
        self.assertIn("python3 -c", plan.execution_command)
        self.assertIn("*.py", plan.execution_command)
        self.assertEqual(plan.filter_hint, "find")

    def test_plan_command_rewrites_phase4_package_commands(self):
        plan = plan_command("uv sync")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("npm list --depth=0")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package --depth=0")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("uv pip install requests")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package requests")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("pnpm outdated --format json")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package --format json")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("pnpm install zod")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package zod")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("npm run build")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package build")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("bundle update rspec")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package rspec")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("npx prisma migrate dev --name init")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package --name init")
        self.assertEqual(plan.filter_hint, "package")

        plan = plan_command("prisma db push --accept-data-loss")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai package --accept-data-loss")
        self.assertEqual(plan.filter_hint, "package")

    def test_plan_command_rewrites_direct_formatter_commands(self):
        plan = plan_command("prettier --check .")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai format --check .")
        self.assertEqual(plan.filter_hint, "format")

        plan = plan_command("pnpm exec prettier --check .")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai format --check .")
        self.assertEqual(plan.filter_hint, "format")

        plan = plan_command("black --check .")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai format --check .")
        self.assertEqual(plan.filter_hint, "format")

        plan = plan_command("biome format src")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai format src")
        self.assertEqual(plan.filter_hint, "format")

        plan = plan_command("biome check --write src")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai format --write src")
        self.assertEqual(plan.filter_hint, "format")

    def test_plan_command_rewrites_phase5_infra_commands(self):
        plan = plan_command("docker ps")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai docker ps")
        self.assertEqual(plan.filter_hint, "docker")

        plan = plan_command("docker compose logs web")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai docker compose logs web")
        self.assertEqual(plan.filter_hint, "docker")

        plan = plan_command("docker compose build api")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai docker compose build api")
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

        plan = plan_command("psql -c 'select 1'")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai psql -c 'select 1'")
        self.assertEqual(plan.filter_hint, "psql")

    def test_plan_command_rewrites_dotnet_family(self):
        plan = plan_command("dotnet build src/App.csproj")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai dotnet build src/App.csproj")
        self.assertEqual(plan.filter_hint, "dotnet")

        plan = plan_command("dotnet test --filter Name~Auth")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai dotnet test --filter Name~Auth")
        self.assertEqual(plan.filter_hint, "dotnet")

        plan = plan_command("dotnet restore")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai dotnet restore")

        plan = plan_command("dotnet format src")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai dotnet format src")

    def test_plan_command_rewrites_phase6_github_and_api_commands(self):
        plan = plan_command("gh pr list")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh pr list")
        self.assertEqual(plan.filter_hint, "gh")
        self.assertEqual(
            plan.execution_command,
            "gh pr list --json number,title,state,author,updatedAt",
        )

        plan = plan_command("gh pr view 42")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh pr view 42")
        self.assertEqual(plan.filter_hint, "gh")
        self.assertEqual(
            plan.execution_command,
            "gh pr view 42 --json number,title,state,author,body,url,mergeable,reviews,statusCheckRollup",
        )

        plan = plan_command("gh issue list")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh issue list")
        self.assertEqual(
            plan.execution_command,
            "gh issue list --json number,title,state,author",
        )

        plan = plan_command("gh run list")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh run list")
        self.assertEqual(
            plan.execution_command,
            "gh run list --json databaseId,name,status,conclusion,createdAt --limit 10",
        )

        plan = plan_command("gh repo view")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh repo view")
        self.assertEqual(plan.filter_hint, "gh")

        plan = plan_command("gh api repos/nasirus/ptk/issues")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.planned_command, "pytk-ai gh api repos/nasirus/ptk/issues"
        )
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

    def test_plan_command_rewrites_graphite_family(self):
        plan = plan_command("gt log")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gt log")
        self.assertEqual(plan.filter_hint, "gt")

        plan = plan_command("gt submit")
        self.assertEqual(plan.planned_command, "pytk-ai gt submit")

        plan = plan_command("gt status")
        self.assertEqual(plan.planned_command, "pytk-ai gt status")

    def test_plan_command_rewrites_batch8_structured_tool_execution(self):
        plan = plan_command("golangci-lint run --timeout 5m")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai golangci-lint run --timeout 5m")
        self.assertEqual(plan.filter_hint, "golangci-lint")
        self.assertIn("golangci-lint --version", plan.execution_command)
        self.assertIn(
            "golangci-lint run --out-format=json --timeout 5m",
            plan.execution_command,
        )

        plan = plan_command("bundle exec rspec spec/models/user_spec.rb")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.execution_command,
            "bundle exec rspec --format json spec/models/user_spec.rb",
        )

        plan = plan_command("rubocop app/models/user.rb")
        self.assertTrue(plan.managed)
        self.assertEqual(
            plan.execution_command, "rubocop --format json app/models/user.rb"
        )

    def test_plan_command_rewrites_git_wrapper_execution_modes(self):
        plan = plan_command("git log")
        self.assertTrue(plan.managed)
        self.assertIn(
            "--pretty=format:%h %s (%ar) <%an>%n%b%n---END---", plan.execution_command
        )
        self.assertIn("-10", plan.execution_command)
        self.assertIn("--no-merges", plan.execution_command)

        plan = plan_command("git branch")
        self.assertEqual(plan.execution_command, "git branch -a --no-color")

        plan = plan_command("git stash show")
        self.assertEqual(plan.execution_command, "git stash show -p")

        plan = plan_command("git worktree")
        self.assertEqual(plan.execution_command, "git worktree list")

    def test_plan_command_keeps_structured_gh_output_raw(self):
        plan = plan_command("gh pr view 42 --json number,title")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "gh-structured-output")

        plan = plan_command("gh repo view --json name,url")
        self.assertFalse(plan.managed)
        self.assertEqual(plan.skip_reason, "gh-structured-output")

    def test_plan_command_keeps_special_gh_pr_view_modes_passthrough(self):
        plan = plan_command("gh pr view 42 --comments")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.planned_command, "pytk-ai gh pr view 42 --comments")
        self.assertEqual(plan.execution_command, "gh pr view 42 --comments")

        plan = plan_command("gh pr view --web 42")
        self.assertTrue(plan.managed)
        self.assertEqual(plan.execution_command, "gh pr view --web 42")
