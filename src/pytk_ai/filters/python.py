from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output


def _pytest_summary(text: str) -> str | None:
    failures: list[str] = []
    current_failure: list[str] = []
    summary_line = ""
    in_failures = False
    in_summary = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("===") and "FAILURES" in stripped:
            in_failures = True
            in_summary = False
            continue
        if stripped.startswith("===") and "short test summary" in stripped.lower():
            in_failures = False
            in_summary = True
            if current_failure:
                failures.append("\n".join(current_failure))
                current_failure = []
            continue
        if stripped.startswith("===") and (
            " passed" in stripped or " failed" in stripped or " error" in stripped
        ):
            summary_line = stripped
            if current_failure:
                failures.append("\n".join(current_failure))
                current_failure = []
            continue
        if in_failures:
            if stripped.startswith("___"):
                if current_failure:
                    failures.append("\n".join(current_failure))
                current_failure = [stripped]
                continue
            if stripped:
                current_failure.append(stripped)
            continue
        if in_summary and stripped.startswith(("FAILED ", "ERROR ")):
            failures.append(stripped)

    if current_failure:
        failures.append("\n".join(current_failure))

    if not failures and summary_line:
        passed_match = re.search(r"(\d+)\s+passed", summary_line)
        if passed_match:
            return f"Pytest: {passed_match.group(1)} passed"
        return f"Pytest: {summary_line}"
    if not failures:
        return None

    result = [f"Pytest: {summary_line}" if summary_line else "Pytest failures"]
    for index, failure in enumerate(failures[:5], start=1):
        lines = failure.splitlines()
        first = lines[0]
        if first.startswith("FAILED "):
            result.append(f"{index}. [FAIL] {first.removeprefix('FAILED ')}")
            if len(lines) > 1:
                result.append(f"   {lines[1]}")
            continue
        result.append(f"{index}. [FAIL] {first.strip('_ ').strip()}")
        for line in lines[1:4]:
            if (
                line.startswith((">", "E"))
                or "assert" in line.lower()
                or "error" in line.lower()
                or ".py:" in line
            ):
                result.append(f"   {line}")
    if len(failures) > 5:
        result.append(f"... +{len(failures) - 5} more failures")
    return "\n".join(result)


_MYPY_DIAG_RE = re.compile(
    r"^(.+?):(\d+)(?::\d+)?:\s+(error|warning|note):\s+(.+?)(?:\s+\[([^\]]+)\])?$"
)


def _mypy_summary(text: str) -> str | None:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    fileless: list[str] = []
    current: dict[str, object] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("Success:"):
            return "mypy: No issues found"
        if line.startswith("Found ") and " error" in line:
            continue
        match = _MYPY_DIAG_RE.match(line)
        if match:
            severity = match.group(3)
            path = match.group(1)
            if severity == "note":
                if current is not None and current["path"] == path:
                    current["notes"].append(match.group(4))
                else:
                    fileless.append(line)
                continue
            current = {
                "path": path,
                "line": match.group(2),
                "code": match.group(5) or "",
                "message": match.group(4),
                "notes": [],
            }
            grouped[path].append(current)
            continue
        if "error:" in line and line.strip():
            fileless.append(line.strip())

    if not grouped and not fileless:
        return "mypy: No issues found"

    code_counter = Counter(
        str(entry["code"])
        for entries in grouped.values()
        for entry in entries
        if entry["code"]
    )
    lines: list[str] = []
    if fileless:
        lines.extend(fileless[:5])
    total = sum(len(entries) for entries in grouped.values())
    if grouped:
        lines.append(f"mypy: {total} errors in {len(grouped)} files")
    if len(code_counter) > 1:
        lines.append(
            "Top codes: "
            + ", ".join(
                f"{code} ({count}x)" for code, count in code_counter.most_common(5)
            )
        )
    for path, entries in sorted(
        grouped.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{path} ({len(entries)})")
        for entry in entries[:4]:
            code = f"[{entry['code']}] " if entry["code"] else ""
            lines.append(f"  L{entry['line']}: {code}{entry['message']}")
            for note in list(entry["notes"])[:2]:
                lines.append(f"    {note}")
    if len(grouped) > 8:
        lines.append(f"... +{len(grouped) - 8} more files")
    return "\n".join(lines)


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
        text = _mypy_summary(combined) or text
        filter_name = "python.mypy"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
