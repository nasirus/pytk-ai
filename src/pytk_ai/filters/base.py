from __future__ import annotations

from functools import lru_cache
import math
import re

from ..models import FilterMetrics, FilterResult, FilterUsageMode, OutputMetrics
from .policy import policy_for_filter_name

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


def combine_command_streams(stdout: str, stderr: str, exit_code: int) -> str:
    stdout = stdout.rstrip()
    stderr = stderr.rstrip()
    if exit_code == 0:
        parts = [part for part in (stdout, stderr) if part]
    else:
        parts = [part for part in (stderr, stdout) if part]
    return "\n".join(parts)


@lru_cache(maxsize=1)
def _load_token_encoder():
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    return tiktoken.get_encoding("cl100k_base")


def token_estimator_label() -> str:
    return "cl100k_base" if _load_token_encoder() is not None else "chars/4-estimate"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _load_token_encoder()
    if encoder is not None:
        return len(encoder.encode(text))
    return max(1, math.ceil(len(text) / 4))


def output_metrics(text: str) -> OutputMetrics:
    return OutputMetrics(
        chars=len(text),
        lines=0 if not text else len(text.splitlines()),
        tokens=estimate_tokens(text),
    )


def build_filter_metrics(
    raw_text: str,
    filtered_text: str,
    *,
    usage_mode: FilterUsageMode,
) -> FilterMetrics:
    raw = output_metrics(raw_text)
    filtered = output_metrics(filtered_text)
    saved_tokens = raw.tokens - filtered.tokens
    saved_pct = ((saved_tokens / raw.tokens) * 100.0) if raw.tokens else 0.0
    return FilterMetrics(
        usage_mode=usage_mode,
        estimator=token_estimator_label(),
        raw=raw,
        filtered=filtered,
        saved_chars=raw.chars - filtered.chars,
        saved_lines=raw.lines - filtered.lines,
        saved_tokens=saved_tokens,
        saved_pct=saved_pct,
    )


def finalize_filter_result(
    result: FilterResult,
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
    usage_mode: FilterUsageMode,
) -> FilterResult:
    raw_text = combine_command_streams(stdout, stderr, exit_code)
    filter_name = result.filter_name
    return FilterResult(
        output=result.output,
        filter_name=filter_name,
        error=result.error,
        truncated=result.truncated,
        metrics=build_filter_metrics(raw_text, result.output, usage_mode=usage_mode),
        policy=policy_for_filter_name(filter_name),
    )


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
