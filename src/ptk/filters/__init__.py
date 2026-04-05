from __future__ import annotations

from ..models import FilterResult
from ..plan import CommandPlan
from ..plan.normalize import infer_filter_hint
from .generic import filter_generic_output
from .git import filter_git_output
from .python import filter_python_output
from .system import filter_system_output

_FILTERS = {
    "find": filter_system_output,
    "git": filter_git_output,
    "grep": filter_system_output,
    "ls": filter_system_output,
    "mypy": filter_python_output,
    "pytest": filter_python_output,
    "read": filter_system_output,
    "ruff": filter_python_output,
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
