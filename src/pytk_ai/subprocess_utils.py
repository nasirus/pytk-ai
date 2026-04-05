from __future__ import annotations

import os
import subprocess

from .models import ExecutionResult


def execute_raw(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> ExecutionResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if not stderr:
            stderr = f"Command timed out after {timeout} seconds"
        return ExecutionResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=124,
            timed_out=True,
            error="timeout",
        )
    except OSError as exc:
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=str(exc),
            exit_code=1,
            error=exc.__class__.__name__,
        )

    return ExecutionResult(
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )
