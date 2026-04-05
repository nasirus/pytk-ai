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
