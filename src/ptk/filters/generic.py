from __future__ import annotations

from ..models import FilterResult
from .base import make_filter_result


def _combine_streams(stdout: str, stderr: str, exit_code: int) -> str:
    stdout = stdout.rstrip()
    stderr = stderr.rstrip()
    if exit_code == 0:
        parts = [part for part in (stdout, stderr) if part]
        return "\n".join(parts)
    parts = [part for part in (stderr, stdout) if part]
    return "\n".join(parts)


def filter_generic_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    combined = _combine_streams(stdout, stderr, exit_code)
    return make_filter_result(
        combined,
        filter_name="generic",
        max_output_lines=max_output_lines,
    )
