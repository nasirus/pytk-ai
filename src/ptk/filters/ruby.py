from __future__ import annotations

import re
from collections import defaultdict

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_RUBOCOP_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<severity>[A-Z]):\s+"
    r"(?P<cop>[A-Za-z0-9/_]+):\s+"
    r"(?P<message>.+)$"
)
_RSPEC_SUMMARY_RE = re.compile(r"(\d+)\s+examples?,\s+(\d+)\s+failures?")


def _compact_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    for prefix in (
        "app/",
        "lib/",
        "spec/",
        "test/",
        "config/",
    ):
        if prefix in normalized:
            return normalized[normalized.find(prefix) :]
    return normalized.rsplit("/", 1)[-1]


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def filter_rubocop_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    combined = _combine_streams(stdout, stderr, exit_code)
    generic = filter_generic_output(
        "",
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for raw_line in combined.splitlines():
        stripped = raw_line.strip()
        match = _RUBOCOP_RE.match(stripped)
        if not match:
            continue
        by_file[match.group("path")].append(
            {
                "line": match.group("line"),
                "cop": match.group("cop"),
                "message": match.group("message"),
                "severity": match.group("severity"),
            }
        )
    if not by_file:
        for line in reversed(combined.splitlines()):
            stripped = line.strip()
            if "no offenses detected" in stripped:
                text = f"ok rubocop ({stripped.split()[0]} files)"
                break
            if "offenses detected" in stripped:
                text = f"rubocop: {stripped}"
                break
        else:
            text = generic.output
        return make_filter_result(
            text,
            filter_name="rubocop",
            max_output_lines=max_output_lines,
            error=generic.error,
        )
    offense_count = sum(len(entries) for entries in by_file.values())
    lines = [f"rubocop: {offense_count} offenses in {len(by_file)} files"]
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for entry in sorted(entries, key=lambda item: (item["severity"], item["line"]))[
            :5
        ]:
            lines.append(
                f"  :{entry['line']} {entry['cop']} - {_truncate(entry['message'])}"
            )
    return make_filter_result(
        "\n".join(lines),
        filter_name="rubocop",
        max_output_lines=max_output_lines,
        error=generic.error,
    )


def filter_rspec_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    combined = _combine_streams(stdout, stderr, exit_code)
    generic = filter_generic_output(
        "",
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    failures: list[str] = []
    current: list[str] = []
    summary = ""
    in_failures = False
    for raw_line in combined.splitlines():
        stripped = raw_line.strip()
        if stripped == "Failures:":
            in_failures = True
            continue
        if stripped == "Failed examples:":
            if current:
                failures.append("\n".join(current))
                current = []
            in_failures = False
            continue
        if _RSPEC_SUMMARY_RE.search(stripped):
            summary = stripped
            if current:
                failures.append("\n".join(current))
                current = []
            continue
        if in_failures:
            if re.match(r"^\d+\)", stripped):
                if current:
                    failures.append("\n".join(current))
                current = [stripped]
            elif stripped and not (
                "/gems/" in stripped
                or "lib/rspec" in stripped
                or "vendor/bundle" in stripped
            ):
                current.append(stripped)
    if current:
        failures.append("\n".join(current))
    if not summary and exit_code == 0 and not failures:
        return make_filter_result(
            "RSpec: passed",
            filter_name="rspec",
            max_output_lines=max_output_lines,
        )
    if not failures:
        text = f"RSpec: {summary}" if summary else generic.output
        return make_filter_result(
            text,
            filter_name="rspec",
            max_output_lines=max_output_lines,
            error=generic.error,
        )
    lines = [f"RSpec: {summary}" if summary else "RSpec failures"]
    for index, failure in enumerate(failures[:5], start=1):
        compact = []
        for line in failure.splitlines():
            compact.append(line)
            if len(compact) >= 4:
                break
        lines.append(f"{index}. " + "\n   ".join(compact))
    if len(failures) > 5:
        lines.append(f"... +{len(failures) - 5} more failures")
    return make_filter_result(
        "\n".join(lines),
        filter_name="rspec",
        max_output_lines=max_output_lines,
        error=generic.error,
    )
