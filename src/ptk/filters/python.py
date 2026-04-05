from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output


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


_RUFF_TEXT_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+):\s+(?P<code>[A-Z]+\d+)\s+(?P<message>.+)$"
)


def _compact_path(path: str) -> str:
    parts = path.split("/")
    if len(parts) <= 3:
        return path
    return "/".join([parts[0], "...", *parts[-2:]])


def _format_ruff_summary(issues: list[dict[str, object]]) -> str:
    total_issues = len(issues)
    total_files = len({str(issue["filename"]) for issue in issues})
    fixable_count = sum(1 for issue in issues if issue.get("fixable"))
    by_rule = Counter(str(issue["code"]) for issue in issues)
    by_file: dict[str, list[dict[str, object]]] = defaultdict(list)
    for issue in issues:
        by_file[str(issue["filename"])].append(issue)

    lines = [f"Ruff: {total_issues} issues in {total_files} files"]
    if fixable_count:
        lines[0] += f" ({fixable_count} fixable)"
    lines.append("Top rules:")
    for code, count in by_rule.most_common(5):
        lines.append(f"  {code} ({count}x)")
    lines.append("Top files:")
    for filename, file_issues in sorted(
        by_file.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[:8]:
        rule_counts = Counter(str(issue["code"]) for issue in file_issues)
        top_rules = ", ".join(
            f"{code} ({count})" for code, count in rule_counts.most_common(3)
        )
        lines.append(
            f"  {_compact_path(filename)} ({len(file_issues)} issues): {top_rules}"
        )
    remaining_files = len(by_file) - min(len(by_file), 8)
    if remaining_files:
        lines.append(f"... +{remaining_files} more files")
    return "\n".join(lines)


def _ruff_summary(text: str, exit_code: int) -> str | None:
    stripped = text.strip()
    if not stripped:
        return "Ruff: no issues found" if exit_code == 0 else None

    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            issues: list[dict[str, object]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                issues.append(
                    {
                        "filename": item.get("filename", "<unknown>"),
                        "code": item.get("code", "<unknown>"),
                        "fixable": item.get("fix") is not None,
                    }
                )
            if not issues:
                return "Ruff: no issues found"
            return _format_ruff_summary(issues)

    issues = []
    for line in stripped.splitlines():
        match = _RUFF_TEXT_RE.match(line.strip())
        if not match:
            continue
        issues.append(
            {
                "filename": match.group("path"),
                "code": match.group("code"),
                "fixable": False,
            }
        )
    if issues:
        return _format_ruff_summary(issues)
    return None


def filter_python_output(
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
    filter_name = "python"
    if "pytest" in command:
        text = _pytest_summary(text) or text
        filter_name = "python.pytest"
    elif "ruff" in command:
        text = _ruff_summary(combined, exit_code) or text
        filter_name = "python.ruff"
    elif "mypy" in command:
        filter_name = "python.mypy"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
