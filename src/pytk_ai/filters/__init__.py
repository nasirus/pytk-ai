from __future__ import annotations

from ..models import FilterResult, FilterUsageMode
from ..plan import CommandPlan
from ..plan.normalize import infer_filter_hint
from .base import finalize_filter_result
from .build import (
    filter_cargo_output,
    filter_lint_output,
    filter_next_output,
    filter_tsc_output,
)
from .dotnet import filter_dotnet_output
from .formatters import filter_format_output
from .files import filter_file_output
from .generic import filter_generic_output
from .github_api import filter_github_api_output
from .git import filter_git_output
from .gt import filter_gt_output
from .go import filter_go_output, filter_golangci_output
from .infra import filter_infra_output
from .packages import filter_package_output
from .psql import filter_psql_output
from .python import filter_python_output
from .ruby import filter_rake_output, filter_rspec_output, filter_rubocop_output
from .system import filter_system_output
from .tests import filter_test_output

_FILTERS = {
    "aws": filter_infra_output,
    "cargo": filter_cargo_output,
    "curl": filter_github_api_output,
    "diff": filter_file_output,
    "docker": filter_infra_output,
    "dotnet": filter_dotnet_output,
    "find": filter_file_output,
    "format": filter_format_output,
    "gh": filter_github_api_output,
    "git": filter_git_output,
    "gt": filter_gt_output,
    "go": filter_go_output,
    "golangci-lint": filter_golangci_output,
    "grep": filter_file_output,
    "kubectl": filter_infra_output,
    "lint": filter_lint_output,
    "ls": filter_system_output,
    "mypy": filter_python_output,
    "next": filter_next_output,
    "npm": filter_package_output,
    "package": filter_package_output,
    "psql": filter_psql_output,
    "pnpm": filter_package_output,
    "prisma": filter_package_output,
    "pytest": filter_python_output,
    "read": filter_file_output,
    "rake": filter_rake_output,
    "rspec": filter_rspec_output,
    "rubocop": filter_rubocop_output,
    "ruff": filter_python_output,
    "test": filter_test_output,
    "playwright": filter_test_output,
    "tree": filter_file_output,
    "tsc": filter_tsc_output,
    "terraform": filter_infra_output,
    "vitest": filter_test_output,
    "bundle": filter_package_output,
    "uv": filter_package_output,
    "wc": filter_file_output,
    "wget": filter_github_api_output,
}


def filter_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    plan: CommandPlan | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> FilterResult:
    filter_hint = (
        plan.filter_hint
        if plan is not None and plan.filter_hint
        else infer_filter_hint(command)
    )
    filter_func = _FILTERS.get(filter_hint, filter_generic_output)
    try:
        return finalize_filter_result(
            filter_func(
                command,
                stdout,
                stderr,
                exit_code,
                max_output_lines=max_output_lines,
            ),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            usage_mode=usage_mode,
        )
    except Exception as exc:
        fallback = filter_generic_output(
            command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
            allow_toml_fallback=False,
        )
        return finalize_filter_result(
            FilterResult(
                output=fallback.output,
                filter_name=fallback.filter_name,
                error=f"{filter_hint or 'unknown'} filter failed: {exc}",
                truncated=fallback.truncated,
            ),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            usage_mode=usage_mode,
        )
