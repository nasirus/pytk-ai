from __future__ import annotations

import re

from ..models import FilterResult
from .base import combine_command_streams, make_filter_result
from .toml_fallback import apply_builtin_fallback


def _combine_streams(stdout: str, stderr: str, exit_code: int) -> str:
    return combine_command_streams(stdout, stderr, exit_code)


def _collect_error_lines(output: str) -> str:
    error_patterns = (
        re.compile(r"(?i)^.*error[\s:\[].*$"),
        re.compile(r"(?i)^.*\berr\b.*$"),
        re.compile(r"(?i)^.*warning[\s:\[].*$"),
        re.compile(r"(?i)^.*\bwarn\b.*$"),
        re.compile(r"(?i)^.*failed.*$"),
        re.compile(r"(?i)^.*failure.*$"),
        re.compile(r"(?i)^.*exception.*$"),
        re.compile(r"(?i)^.*panic.*$"),
        re.compile(r"^error\[E\d+\]:.*$"),
        re.compile(r"^\s*--> .*:\d+:\d+$"),
        re.compile(r"^Traceback.*$"),
        re.compile(r'^\s*File ".*", line \d+.*$'),
        re.compile(r"^\s*at .*:\d+:\d+.*$"),
        re.compile(r"^.*\.go:\d+:.*$"),
    )
    result: list[str] = []
    in_error_block = False
    blank_count = 0

    for line in output.splitlines():
        is_error_line = any(pattern.search(line) for pattern in error_patterns)
        if is_error_line:
            in_error_block = True
            blank_count = 0
            result.append(line)
            continue
        if not in_error_block:
            continue
        if not line.strip():
            blank_count += 1
            if blank_count >= 2:
                in_error_block = False
            else:
                result.append(line)
            continue
        if line.startswith((" ", "\t")):
            result.append(line)
            blank_count = 0
            continue
        in_error_block = False

    return "\n".join(result)


def filter_errors_only_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    combined = combine_command_streams(stdout, stderr, exit_code)
    filtered = _collect_error_lines(combined)
    if filtered.strip():
        text = filtered
    elif exit_code == 0:
        text = "[ok] Command completed successfully (no errors)"
    else:
        lines = [line for line in combined.splitlines() if line.strip()]
        tail = "\n".join(f"  {line}" for line in lines[-10:])
        text = f"[FAIL] Command failed (exit code: {exit_code})"
        if tail:
            text = f"{text}\n{tail}"
    return make_filter_result(
        text,
        filter_name="err",
        max_output_lines=max_output_lines,
    )


def filter_generic_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
    allow_toml_fallback: bool = True,
) -> FilterResult:
    combined = combine_command_streams(stdout, stderr, exit_code)
    if allow_toml_fallback:
        fallback = apply_builtin_fallback(command, combined)
        if fallback is not None:
            filter_name, filtered = fallback
            return make_filter_result(
                filtered,
                filter_name=filter_name,
                max_output_lines=max_output_lines,
            )
    return make_filter_result(
        combined,
        filter_name="generic",
        max_output_lines=max_output_lines,
    )
