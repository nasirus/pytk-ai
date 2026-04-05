from __future__ import annotations

from ..models import FilterResult
from .base import collapse_repeated_lines, make_filter_result, strip_ansi
from .generic import _combine_streams
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
    combined = _combine_streams(stdout, stderr, exit_code)
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
    elif command.strip().startswith("cat "):
        text = strip_ansi(combined.replace("\r", "\n")).rstrip()
        filter_name = "system.read.cat"
    elif command.strip().startswith("head "):
        text = strip_ansi(combined.replace("\r", "\n")).rstrip()
        filter_name = "system.read.head"
    elif command.strip().startswith("tail "):
        text = collapse_repeated_lines(
            strip_ansi(combined.replace("\r", "\n")).rstrip(),
            max_run=1,
        )
        filter_name = "system.read.tail"
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
