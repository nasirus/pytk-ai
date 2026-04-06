from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess

from .models import ExecutionResult

_SRC_ROOT = Path(__file__).resolve().parents[1]


def _rewrite_local_pytk_command(command: str) -> str:
    stripped = command.lstrip()
    if not stripped.startswith("pytk-ai"):
        return command

    try:
        tokens = shlex.split(command)
    except ValueError:
        return command

    if not tokens or tokens[0] != "pytk-ai":
        return command

    pythonpath = shlex.quote(str(_SRC_ROOT))
    rewritten = shlex.join(["python3", "-m", "pytk_ai", *tokens[1:]])
    return f"PYTHONPATH={pythonpath}${{PYTHONPATH:+:$PYTHONPATH}} {rewritten}"


def execute_raw(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> ExecutionResult:
    command = _rewrite_local_pytk_command(command)
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
