from __future__ import annotations

from ..models import FilterResult
from .base import make_filter_result
from .generic import filter_generic_output


def _pytest_summary(text: str) -> str | None:
    lines = text.splitlines()
    summary_lines = [
        line
        for line in lines
        if "short test summary info" in line.lower()
        or line.startswith(("FAILED ", "ERROR "))
        or (" passed" in line and " in " in line)
        or (" failed" in line and " in " in line)
        or (" errors" in line and " in " in line)
    ]
    if not summary_lines:
        return None
    return "\n".join(summary_lines)


def filter_python_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    generic = filter_generic_output(
        command,
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    text = generic.output
    filter_name = "python"
    if "pytest" in command:
        text = _pytest_summary(text) or text
        filter_name = "python.pytest"
    elif "ruff" in command:
        filter_name = "python.ruff"
    elif "mypy" in command:
        filter_name = "python.mypy"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
