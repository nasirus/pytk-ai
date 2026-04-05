from __future__ import annotations

from ..models import FilterPolicy

_SUCCESS_ONLY_PREFIXES = (
    "curl",
    "docker.",
    "files.diff",
    "files.tree",
    "files.wc",
    "gh.",
    "git.add",
    "git.commit",
    "git.fetch",
    "git.pull",
    "git.push",
    "git.stash",
    "git.worktree",
    "kubectl.logs",
    "kubectl.pods",
    "kubectl.services",
    "npm.list",
    "pip.list",
    "pip.outdated",
    "pnpm.list",
    "prisma.generate",
    "search.find",
    "search.grep",
    "system.ls",
    "system.read.",
    "terraform.plan",
    "terraform.validate",
    "uv.sync",
    "wget",
)

_BOTH_PREFIXES = (
    "aws.read",
    "bundle.install",
    "cargo.",
    "git.branch",
    "git.diff",
    "git.log",
    "git.show",
    "go.",
    "golangci-lint",
    "lint.",
    "next.build",
    "python.",
    "rspec",
    "rubocop",
    "test.",
)

_SUCCESS_ONLY_POLICY = FilterPolicy(
    summary_scope="success-only",
    usage_mode_behavior="same-output",
    notes="Summarize successful output and preserve actionable failure details.",
)

_FAILURE_ONLY_POLICY = FilterPolicy(
    summary_scope="failure-only",
    usage_mode_behavior="same-output",
    notes="Reserved for commands where only failure output should be compacted.",
)

_BOTH_POLICY = FilterPolicy(
    summary_scope="both",
    usage_mode_behavior="same-output",
    notes="Summarize successful and failing output, while still falling back to raw text when parsing is unsafe.",
)


def policy_for_filter_name(filter_name: str | None) -> FilterPolicy:
    if not filter_name:
        return _BOTH_POLICY
    if any(filter_name.startswith(prefix) for prefix in _SUCCESS_ONLY_PREFIXES):
        return _SUCCESS_ONLY_POLICY
    if any(filter_name.startswith(prefix) for prefix in _BOTH_PREFIXES):
        return _BOTH_POLICY
    return (
        _FAILURE_ONLY_POLICY if filter_name == "reserved.failure-only" else _BOTH_POLICY
    )
