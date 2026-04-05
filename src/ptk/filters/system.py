from __future__ import annotations

from ..models import FilterResult
from .base import make_filter_result
from .generic import filter_generic_output


def _strip_ls_total(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("total "):
        lines = lines[1:]
    return "\n".join(lines)


def filter_system_output(
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
    filter_name = "system"
    if command.strip().startswith("ls"):
        text = _strip_ls_total(text)
        filter_name = "system.ls"
    elif command.strip().startswith(("cat ", "head ", "tail ")):
        filter_name = "system.read"
    elif command.strip().startswith(("grep ", "rg ")):
        filter_name = "system.grep"
    elif command.strip().startswith("find"):
        filter_name = "system.find"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
