from __future__ import annotations

import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams


_TEST_SUMMARY_PATTERNS = (
    re.compile(r"^test result:\s+.+$", re.IGNORECASE),
    re.compile(r"^Test Suites:\s+.+$"),
    re.compile(r"^Tests:\s+.+$"),
    re.compile(r"^\d+\s+(?:passed|failed|skipped).+\bin\s+\d"),
    re.compile(r"^Ran \d+ tests? in "),
)
_FAILURE_PATTERNS = (
    re.compile(r"^failures:$", re.IGNORECASE),
    re.compile(r"^FAILED\b"),
    re.compile(r"^FAIL\b"),
    re.compile(r"^ERROR\b"),
    re.compile(r"^thread '.*' panicked at "),
    re.compile(r"^assertion `.*` failed"),
    re.compile(r"^\s*at .+:\d+:\d+"),
    re.compile(r"^\s+[A-Za-z0-9_:/.-]+$"),
)


def _generic_test_summary(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    summary_lines: list[str] = []
    failure_lines: list[str] = []
    in_failures = False
    saw_failure_entry = False

    for line in lines:
        stripped = line.strip()
        if any(pattern.search(stripped) for pattern in _TEST_SUMMARY_PATTERNS):
            summary_lines.append(stripped)
        if stripped.lower() == "failures:":
            in_failures = True
            saw_failure_entry = False
            failure_lines.append("failures:")
            continue
        if any(pattern.search(stripped) for pattern in _FAILURE_PATTERNS):
            failure_lines.append(stripped)
            continue
        if in_failures:
            if not stripped:
                if saw_failure_entry:
                    in_failures = False
                continue
            if line.startswith((" ", "\t")):
                failure_lines.append(stripped)
                saw_failure_entry = True
                continue
            in_failures = False

    if failure_lines:
        return "\n".join(failure_lines[:20] + summary_lines[:5])
    if summary_lines:
        return "\n".join(summary_lines[:8])
    tail = [line.strip() for line in lines if line.strip()][-8:]
    return "\n".join(tail)


def _filter_cargo_test(text: str) -> str:
    summary = _generic_test_summary(text)
    if "test result:" in summary:
        return summary
    result_lines = [
        line.strip() for line in text.splitlines() if "test result:" in line
    ]
    if result_lines:
        if summary:
            return "\n".join(summary.splitlines() + result_lines[-1:])
        return result_lines[-1]
    return summary


def filter_test_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    combined = _combine_streams(stdout, stderr, exit_code)
    lowered = command.lower()
    if "cargo test" in lowered:
        text = _filter_cargo_test(combined)
        filter_name = "test.cargo"
    else:
        text = _generic_test_summary(combined)
        filter_name = "test.generic"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
    )
