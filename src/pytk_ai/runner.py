from __future__ import annotations

from .filters import filter_output
from .models import CommandResult, FilterUsageMode
from .plan import plan_command
from .subprocess_utils import execute_raw


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
