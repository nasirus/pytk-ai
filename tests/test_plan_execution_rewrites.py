import unittest

from pytk_ai.plan.execution_rewrites import (
    ExecutionRewriteContext,
    rewrite_execution_command,
)


class PlanExecutionRewritesTests(unittest.TestCase):
    def test_rewrite_execution_command_rewrites_bare_git_status(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="FOO=1 git status > out.txt 2>&1",
                prefix="FOO=1 ",
                normalized_command="git status",
                rest="status",
                redirect_suffix=" > out.txt 2>&1",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(
            result,
            "FOO=1 git status --porcelain=v1 --branch > out.txt 2>&1",
        )

    def test_rewrite_execution_command_preserves_git_status_with_args(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git status --short",
                prefix="",
                normalized_command="git status --short",
                rest="status --short",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(result, "git status --short")

    def test_rewrite_execution_command_rewrites_git_log_defaults(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git log",
                prefix="",
                normalized_command="git log",
                rest="log",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertIn("git log", result)
        self.assertIn("--pretty=format:%h %s (%ar) <%an>%n%b%n---END---", result)
        self.assertIn("-10", result)
        self.assertIn("--no-merges", result)

    def test_rewrite_execution_command_rewrites_git_diff_default_mode(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git diff",
                prefix="",
                normalized_command="git diff",
                rest="diff",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertIn("git diff --stat", result)
        self.assertIn("--- Changes ---", result)

    def test_rewrite_execution_command_preserves_git_diff_stat_mode(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git diff --stat",
                prefix="",
                normalized_command="git diff --stat",
                rest="diff --stat",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(result, "git diff --stat")

    def test_rewrite_execution_command_rewrites_git_branch_default_listing(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git branch",
                prefix="",
                normalized_command="git branch",
                rest="branch",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(result, "git branch -a --no-color")

    def test_rewrite_execution_command_rewrites_git_stash_show_to_patch(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git stash show",
                prefix="",
                normalized_command="git stash show",
                rest="stash show",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(result, "git stash show -p")

    def test_rewrite_execution_command_rewrites_git_worktree_default_list(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="git worktree",
                prefix="",
                normalized_command="git worktree",
                rest="worktree",
                redirect_suffix="",
                filter_hint="git",
                matched_rule="pytk-ai git",
            )
        )
        self.assertEqual(result, "git worktree list")

    def test_rewrite_execution_command_rewrites_gh_pr_list_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="gh pr list",
                prefix="",
                normalized_command="gh pr list",
                rest="pr list",
                redirect_suffix="",
                filter_hint="gh",
                matched_rule="pytk-ai gh",
            )
        )
        self.assertEqual(
            result,
            "gh pr list --json number,title,state,author,updatedAt",
        )

    def test_rewrite_execution_command_rewrites_gh_pr_view_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="gh pr view 42",
                prefix="",
                normalized_command="gh pr view 42",
                rest="pr view 42",
                redirect_suffix="",
                filter_hint="gh",
                matched_rule="pytk-ai gh",
            )
        )
        self.assertEqual(
            result,
            "gh pr view 42 --json number,title,state,author,body,url,mergeable,reviews,statusCheckRollup",
        )

    def test_rewrite_execution_command_preserves_gh_pr_view_comments_mode(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="gh pr view 42 --comments",
                prefix="",
                normalized_command="gh pr view 42 --comments",
                rest="pr view 42 --comments",
                redirect_suffix="",
                filter_hint="gh",
                matched_rule="pytk-ai gh",
            )
        )
        self.assertEqual(result, "gh pr view 42 --comments")

    def test_rewrite_execution_command_rewrites_gh_issue_list_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="gh issue list --author mona",
                prefix="",
                normalized_command="gh issue list --author mona",
                rest="issue list --author mona",
                redirect_suffix="",
                filter_hint="gh",
                matched_rule="pytk-ai gh",
            )
        )
        self.assertEqual(
            result,
            "gh issue list --json number,title,state,author --author mona",
        )

    def test_rewrite_execution_command_rewrites_gh_run_list_to_json_with_limit(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="gh run list --branch main",
                prefix="",
                normalized_command="gh run list --branch main",
                rest="run list --branch main",
                redirect_suffix="",
                filter_hint="gh",
                matched_rule="pytk-ai gh",
            )
        )
        self.assertEqual(
            result,
            "gh run list --json databaseId,name,status,conclusion,createdAt --limit 10 --branch main",
        )

    def test_rewrite_execution_command_rewrites_golangci_lint_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="golangci-lint run --timeout 5m",
                prefix="",
                normalized_command="golangci-lint run --timeout 5m",
                rest="run --timeout 5m",
                redirect_suffix="",
                filter_hint="golangci-lint",
                matched_rule="pytk-ai golangci-lint",
            )
        )
        self.assertIn("golangci-lint --version", result)
        self.assertIn("golangci-lint run --out-format=json --timeout 5m", result)
        self.assertIn(
            "golangci-lint run --output.json.path stdout --timeout 5m", result
        )

    def test_rewrite_execution_command_rewrites_rspec_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="bundle exec rspec spec/models/user_spec.rb",
                prefix="",
                normalized_command="bundle exec rspec spec/models/user_spec.rb",
                rest="spec/models/user_spec.rb",
                redirect_suffix="",
                filter_hint="rspec",
                matched_rule="pytk-ai rspec",
            )
        )
        self.assertEqual(
            result,
            "bundle exec rspec --format json spec/models/user_spec.rb",
        )

    def test_rewrite_execution_command_preserves_rspec_with_explicit_format(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="rspec --format documentation",
                prefix="",
                normalized_command="rspec --format documentation",
                rest="--format documentation",
                redirect_suffix="",
                filter_hint="rspec",
                matched_rule="pytk-ai rspec",
            )
        )
        self.assertEqual(result, "rspec --format documentation")

    def test_rewrite_execution_command_rewrites_rubocop_to_json(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="rubocop app/models/user.rb",
                prefix="",
                normalized_command="rubocop app/models/user.rb",
                rest="app/models/user.rb",
                redirect_suffix="",
                filter_hint="rubocop",
                matched_rule="pytk-ai rubocop",
            )
        )
        self.assertEqual(result, "rubocop --format json app/models/user.rb")

    def test_rewrite_execution_command_preserves_rubocop_autocorrect_mode(self):
        result = rewrite_execution_command(
            ExecutionRewriteContext(
                trimmed="rubocop -A",
                prefix="",
                normalized_command="rubocop -A",
                rest="-A",
                redirect_suffix="",
                filter_hint="rubocop",
                matched_rule="pytk-ai rubocop",
            )
        )
        self.assertEqual(result, "rubocop -A")
