from __future__ import annotations

import re
import shlex

from ..models import FilterResult, FilterUsageMode
from ..plan import CommandPlan
from ..plan.models import PlanSegment
from ..plan.normalize import infer_filter_hint, strip_trailing_redirect_suffix
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

_CD_FAILURE_RE = re.compile(r"(?m)^(?:[^:\n]+:\s+)*cd:\s")


def _is_cdpath_safe_target(path: str) -> bool:
    return path in {".", ".."} or path.startswith(("/", "./", "../", "~"))


def _is_safe_file_filter_prefix(segment: PlanSegment) -> bool:
    if segment.managed or segment.filter_hint != "cd" or segment.operator != "&&":
        return False
    try:
        tokens = shlex.split(segment.original)
    except ValueError:
        return False
    return (
        len(tokens) == 2
        and tokens[0] == "cd"
        and tokens[1] != "-"
        and _is_cdpath_safe_target(tokens[1])
    )


def _has_trailing_command_terminator(command: str, *, segment: PlanSegment) -> bool:
    return segment.operator == ";" and command.rstrip().endswith(";")


def _is_noop_true_tail_segment(command: str, *, segment: PlanSegment) -> bool:
    if segment.managed or segment.filter_hint != "true":
        return False
    if segment.original.strip() != "true":
        return False
    if segment.operator is None:
        return True
    return _has_trailing_command_terminator(command, segment=segment)


def _is_safe_file_filter_segment(
    command: str,
    *,
    segments: tuple[PlanSegment, ...],
    index: int,
    segment: PlanSegment,
    stderr: str,
) -> bool:
    if index == len(segments) - 1:
        if segment.operator is None:
            return True
        return _has_trailing_command_terminator(command, segment=segment)

    if segment.operator != "||":
        return False

    tail_index = index + 1
    if tail_index != len(segments) - 1:
        return False
    if not _is_noop_true_tail_segment(command, segment=segments[tail_index]):
        return False
    if stderr.strip():
        return False
    _, redirect_suffix = strip_trailing_redirect_suffix(segment.original.strip())
    if redirect_suffix:
        return False
    return bool(segment.original.strip())


def _effective_filter_command(
    command: str,
    *,
    plan: CommandPlan | None,
    filter_hint: str | None,
    stderr: str,
) -> str | None:
    if plan is None or not plan.segments:
        return command

    if filter_hint:
        for index, segment in enumerate(plan.segments):
            if segment.filter_hint != filter_hint:
                continue
            if not segment.managed:
                continue
            if not _is_safe_file_filter_segment(
                command,
                segments=plan.segments,
                index=index,
                segment=segment,
                stderr=stderr,
            ):
                return None
            if any(
                not _is_safe_file_filter_prefix(prefix)
                for prefix in plan.segments[:index]
            ):
                return None
            if index > 0 and _CD_FAILURE_RE.search(stderr):
                return None
            return segment.original

    for segment in plan.segments:
        if segment.managed:
            return None

    return command


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
    effective_command = command
    if filter_func is filter_file_output:
        effective_command = _effective_filter_command(
            command,
            plan=plan,
            filter_hint=filter_hint,
            stderr=stderr,
        )
        if effective_command is None:
            filter_func = filter_generic_output
            effective_command = command
    try:
        return finalize_filter_result(
            filter_func(
                effective_command,
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
