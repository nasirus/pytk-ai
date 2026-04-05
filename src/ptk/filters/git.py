from __future__ import annotations

from ..models import FilterResult
from .base import make_filter_result
from .generic import filter_generic_output


def _drop_advice_lines(text: str) -> str:
    lines = [
        line for line in text.splitlines() if not line.lstrip().startswith('(use "git ')
    ]
    return "\n".join(lines)


def filter_git_output(
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
    text = _drop_advice_lines(generic.output)
    filter_name = "git.status" if " status" in command else "git"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
