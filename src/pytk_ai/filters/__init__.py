from __future__ import annotations

from ..models import FilterResult
from ..plan import CommandPlan
from ..plan.normalize import infer_filter_hint
from .build import (
    filter_cargo_output,
    filter_lint_output,
    filter_next_output,
    filter_tsc_output,
)
from .files import filter_file_output
from .generic import filter_generic_output
from .git import filter_git_output
from .go import filter_go_output, filter_golangci_output
from .packages import filter_package_output
from .python import filter_python_output
from .ruby import filter_rspec_output, filter_rubocop_output
from .system import filter_system_output
from .tests import filter_test_output

_FILTERS = {
    "cargo": filter_cargo_output,
    "diff": filter_file_output,
    "find": filter_file_output,
    "git": filter_git_output,
    "go": filter_go_output,
    "golangci-lint": filter_golangci_output,
    "grep": filter_file_output,
    "lint": filter_lint_output,
    "ls": filter_system_output,
    "mypy": filter_python_output,
    "next": filter_next_output,
    "package": filter_package_output,
    "pytest": filter_python_output,
    "read": filter_file_output,
    "rspec": filter_rspec_output,
    "rubocop": filter_rubocop_output,
    "ruff": filter_python_output,
    "test": filter_test_output,
    "tree": filter_file_output,
    "tsc": filter_tsc_output,
    "wc": filter_file_output,
}


def filter_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    plan: CommandPlan | None = None,
    max_output_lines: int = 200,
) -> FilterResult:
    filter_hint = (
        plan.filter_hint
        if plan is not None and plan.filter_hint
        else infer_filter_hint(command)
    )
    filter_func = _FILTERS.get(filter_hint, filter_generic_output)
    try:
        return filter_func(
            command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )
    except Exception as exc:
        fallback = filter_generic_output(
            command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )
        return FilterResult(
            output=fallback.output,
            filter_name=fallback.filter_name,
            error=f"{filter_hint or 'unknown'} filter failed: {exc}",
            truncated=fallback.truncated,
        )
