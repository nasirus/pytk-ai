from __future__ import annotations

import os
from pathlib import Path
import shlex

from .filters import filter_output
from .filters.generic import filter_errors_only_output
from .filters.system_tools import (
    merged_environment,
    raw_env_text,
    render_env_output,
    render_json_output,
    render_log_output,
    render_smart_output,
    render_summary_output,
    summarize_dependency_directory,
    validate_json_extension,
)
from .models import CommandResult, FilterUsageMode
from .plan import plan_command
from .subprocess_utils import execute_raw


def run_test_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai test",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    execution = execute_raw(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "test", command])
    filtered = filter_output(
        wrapper_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def run_err_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai err",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    execution = execute_raw(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "err", command])
    filtered = filter_errors_only_output(
        wrapper_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def _detect_formatter(args: list[str], *, cwd: str | None = None) -> str:
    if args and args[0] in {"prettier", "black", "ruff", "biome"}:
        return args[0]

    base_dir = Path(cwd or os.getcwd())
    pyproject_path = base_dir / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "[tool.black]" in content:
            return "black"
        if "[tool.ruff.format]" in content or "[tool.ruff]" in content:
            return "ruff"

    if any(
        (base_dir / name).exists()
        for name in (
            "package.json",
            ".prettierrc",
            ".prettierrc.json",
            ".prettierrc.js",
        )
    ):
        return "prettier"

    return "ruff"


def _format_execution_command(formatter: str, user_args: list[str]) -> str:
    if formatter == "prettier":
        command = ["npx", "prettier"]
    elif formatter == "biome":
        command = ["npx", "biome"]
    else:
        command = [formatter]

    if formatter == "black" and not any(
        arg in {"--check", "--diff"} for arg in user_args
    ):
        command.append("--check")
    if formatter == "ruff" and (not user_args or user_args[0] != "format"):
        command.append("format")

    command.extend(user_args)
    if user_args and all(arg.startswith("-") for arg in user_args):
        command.append(".")

    return shlex.join(command)


def run_format_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai format",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    user_args = shlex.split(command)
    formatter = _detect_formatter(user_args, cwd=cwd)
    if user_args and user_args[0] == formatter:
        user_args = user_args[1:]

    executed_command = _format_execution_command(formatter, user_args)
    execution = execute_raw(
        executed_command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "format", *shlex.split(command)])
    filter_command = shlex.join([formatter, *user_args])
    filtered = filter_output(
        filter_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=executed_command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def run_psql_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai psql",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    executed_command = shlex.join(["psql", *shlex.split(command)])
    execution = execute_raw(
        executed_command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "psql", *shlex.split(command)])
    filtered = filter_output(
        executed_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=executed_command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def run_dotnet_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai dotnet",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    user_args = shlex.split(command)
    if user_args and user_args[0] == "dotnet":
        user_args = user_args[1:]

    executed_command = shlex.join(["dotnet", *user_args])
    execution = execute_raw(
        executed_command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "dotnet", *user_args])
    filtered = filter_output(
        executed_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=executed_command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def run_gt_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="pytk-ai gt",
            managed=True,
            changed=bool(command),
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    user_args = shlex.split(command)
    if user_args and user_args[0] == "gt":
        user_args = user_args[1:]

    git_like = {
        "status",
        "diff",
        "show",
        "add",
        "push",
        "pull",
        "fetch",
        "stash",
        "worktree",
    }
    first = user_args[0] if user_args else ""
    if first in git_like:
        executed_command = shlex.join(["git", *user_args])
        filter_command = executed_command
    else:
        executed_command = shlex.join(["gt", *user_args])
        filter_command = executed_command

    execution = execute_raw(
        executed_command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    wrapper_command = shlex.join(["pytk-ai", "gt", *user_args])
    filtered = filter_output(
        filter_command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=executed_command,
        planned_command=wrapper_command,
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )


def _empty_wrapper_result(command: str, planned_command: str) -> CommandResult:
    return CommandResult(
        original_command=command,
        executed_command="",
        planned_command=planned_command,
        managed=True,
        changed=bool(command),
        stdout="",
        stderr="",
        filtered_output="",
        exit_code=1,
        error="empty-command",
        skip_reason="empty-command",
        filter_metrics=None,
        filter_policy=None,
    )


def run_json_command(
    file: str,
    *,
    schema_only: bool = False,
    max_depth: int = 3,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not file.strip():
        return _empty_wrapper_result(file, "pytk-ai json")
    if file == "-":
        content = ""
        executed_command = "stdin"
    else:
        path_error = validate_json_extension(file)
        if path_error is not None:
            return CommandResult(
                original_command=file,
                executed_command=file,
                planned_command=shlex.join(["pytk-ai", "json", file]),
                managed=True,
                changed=True,
                stdout="",
                stderr=path_error,
                filtered_output=path_error,
                exit_code=1,
                error=path_error,
                skip_reason=None,
                filter_metrics=None,
                filter_policy=None,
            )
        content = Path(file).read_text(encoding="utf-8")
        executed_command = file
    rendered = render_json_output(content, max_depth=max_depth, schema_only=schema_only)
    return CommandResult(
        original_command=file,
        executed_command=executed_command,
        planned_command=shlex.join(["pytk-ai", "json", file]),
        managed=True,
        changed=True,
        stdout=content,
        stderr="",
        filtered_output=rendered,
        exit_code=0,
        filter_name="json.schema" if schema_only else "json.compact",
        filter_metrics=None,
        filter_policy=None,
    )


def run_log_command(
    content_or_path: str,
    *,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not content_or_path.strip():
        return _empty_wrapper_result(content_or_path, "pytk-ai log")
    path = Path(content_or_path)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        executed_command = str(path)
    else:
        content = content_or_path
        executed_command = "stdin"
    rendered = render_log_output(content)
    return CommandResult(
        original_command=content_or_path,
        executed_command=executed_command,
        planned_command=shlex.join(["pytk-ai", "log", content_or_path]),
        managed=True,
        changed=True,
        stdout=content,
        stderr="",
        filtered_output=rendered,
        exit_code=0,
        filter_name="log",
        filter_metrics=None,
        filter_policy=None,
    )


def run_env_command(
    filter_text: str | None = None,
    *,
    show_all: bool = False,
    env: dict[str, str] | None = None,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    env_vars = merged_environment(env)
    rendered = render_env_output(env_vars, filter_text=filter_text, show_all=show_all)
    original = filter_text or ""
    planned_parts = ["pytk-ai", "env"]
    if show_all:
        planned_parts.append("--all")
    if filter_text:
        planned_parts.append(filter_text)
    return CommandResult(
        original_command=original,
        executed_command="env",
        planned_command=shlex.join(planned_parts),
        managed=True,
        changed=True,
        stdout=raw_env_text(env_vars),
        stderr="",
        filtered_output=rendered,
        exit_code=0,
        filter_name="env",
        filter_metrics=None,
        filter_policy=None,
    )


def run_deps_command(
    path: str,
    *,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    target = path or "."
    raw, rendered = summarize_dependency_directory(target)
    return CommandResult(
        original_command=target,
        executed_command=target,
        planned_command=shlex.join(["pytk-ai", "deps", target]),
        managed=True,
        changed=True,
        stdout=raw,
        stderr="",
        filtered_output=rendered,
        exit_code=0,
        filter_name="deps",
        filter_metrics=None,
        filter_policy=None,
    )


def run_summary_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return _empty_wrapper_result(command, "pytk-ai summary")
    execution = execute_raw(command, cwd=cwd, env=env, timeout=timeout)
    combined = execution.stdout.rstrip()
    if execution.stderr.rstrip():
        combined = f"{combined}\n{execution.stderr.rstrip()}".strip()
    rendered = render_summary_output(command, combined, execution.exit_code == 0)
    return CommandResult(
        original_command=command,
        executed_command=command,
        planned_command=shlex.join(["pytk-ai", "summary", command]),
        managed=True,
        changed=True,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=rendered,
        exit_code=execution.exit_code,
        filter_name="summary",
        error=execution.error,
        skip_reason=None,
        filter_metrics=None,
        filter_policy=None,
    )


def run_smart_command(
    file: str,
    *,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not file.strip():
        return _empty_wrapper_result(file, "pytk-ai smart")
    content = Path(file).read_text(encoding="utf-8")
    rendered = render_smart_output(content, file)
    return CommandResult(
        original_command=file,
        executed_command=file,
        planned_command=shlex.join(["pytk-ai", "smart", file]),
        managed=True,
        changed=True,
        stdout=content,
        stderr="",
        filtered_output=rendered,
        exit_code=0,
        filter_name="smart",
        filter_metrics=None,
        filter_policy=None,
    )


def run_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    plan: bool = True,
    excluded: tuple[str, ...] | None = None,
    max_output_lines: int = 200,
    usage_mode: FilterUsageMode = "interactive",
) -> CommandResult:
    if not command.strip():
        return CommandResult(
            original_command=command,
            executed_command="",
            planned_command="",
            managed=False,
            changed=False,
            stdout="",
            stderr="",
            filtered_output="",
            exit_code=1,
            error="empty-command",
            skip_reason="empty-command",
            filter_metrics=None,
            filter_policy=None,
        )

    command_plan = plan_command(command, excluded=excluded) if plan else None
    executed_command = command_plan.execution_command if command_plan else command
    execution = execute_raw(
        executed_command,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    filtered = filter_output(
        command,
        execution.stdout,
        execution.stderr,
        execution.exit_code,
        plan=command_plan,
        max_output_lines=max_output_lines,
        usage_mode=usage_mode,
    )
    errors = [error for error in (execution.error, filtered.error) if error]
    return CommandResult(
        original_command=command,
        executed_command=executed_command,
        planned_command=command_plan.planned_command if command_plan else command,
        managed=command_plan.managed if command_plan else False,
        changed=command_plan.changed if command_plan else False,
        stdout=execution.stdout,
        stderr=execution.stderr,
        filtered_output=filtered.output,
        exit_code=execution.exit_code,
        filter_name=filtered.filter_name,
        error="; ".join(errors) if errors else None,
        skip_reason=command_plan.skip_reason if command_plan else None,
        filter_metrics=filtered.metrics,
        filter_policy=filtered.policy,
    )
