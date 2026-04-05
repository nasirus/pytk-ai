from __future__ import annotations

import re

from ..models import FilterResult

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def collapse_blank_lines(text: str) -> str:
    lines = text.splitlines()
    collapsed: list[str] = []
    blank_run = 0
    for line in lines:
        if line.strip():
            blank_run = 0
            collapsed.append(line.rstrip())
            continue
        blank_run += 1
        if blank_run <= 2:
            collapsed.append("")
    return "\n".join(collapsed).strip()


def collapse_repeated_lines(text: str, max_run: int = 2) -> str:
    lines = text.splitlines()
    collapsed: list[str] = []
    previous: str | None = None
    run = 0
    omitted = 0
    for line in lines:
        if line == previous:
            run += 1
            if run <= max_run:
                collapsed.append(line)
            else:
                omitted += 1
            continue
        if omitted:
            collapsed.append(f"... repeated line omitted {omitted} time(s) ...")
            omitted = 0
        previous = line
        run = 1
        collapsed.append(line)
    if omitted:
        collapsed.append(f"... repeated line omitted {omitted} time(s) ...")
    return "\n".join(collapsed)


def truncate_lines(text: str, max_lines: int) -> tuple[str, bool]:
    if max_lines <= 0:
        return "", bool(text.strip())
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text.strip(), False
    head_count = max(1, max_lines // 2)
    tail_count = max_lines - head_count - 1
    if tail_count <= 0:
        kept = lines[:max_lines]
    else:
        kept = (
            lines[:head_count]
            + [f"... {len(lines) - head_count - tail_count} more lines omitted ..."]
            + lines[-tail_count:]
        )
    return "\n".join(kept).strip(), True


def make_filter_result(
    text: str,
    *,
    filter_name: str,
    max_output_lines: int,
    error: str | None = None,
) -> FilterResult:
    cleaned = collapse_repeated_lines(
        collapse_blank_lines(strip_ansi(text.replace("\r", "\n")))
    )
    truncated_text, truncated = truncate_lines(cleaned, max_output_lines)
    return FilterResult(
        output=truncated_text,
        filter_name=filter_name,
        error=error,
        truncated=truncated,
    )
