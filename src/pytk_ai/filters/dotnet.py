from __future__ import annotations

import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_ISSUE_RE = re.compile(
    r"^(?:(?P<path>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s+)?"
    r"(?P<severity>error|warning)\s+"
    r"(?:(?P<code>[A-Z]{2,}\d+)\s*:\s*)?"
    r"(?P<message>.+)$",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"Time Elapsed\s+(?P<duration>\S+)", re.IGNORECASE)
_PROJECT_RE = re.compile(
    r"(?P<project>[^\s\"]+\.(?:csproj|fsproj|vbproj))", re.IGNORECASE
)
_TEST_SUMMARY_RE = re.compile(
    r"Failed:\s*(?P<failed>\d+),\s*Passed:\s*(?P<passed>\d+),\s*"
    r"Skipped:\s*(?P<skipped>\d+),\s*Total:\s*(?P<total>\d+),\s*"
    r"Duration:\s*(?P<duration>.+?)(?:\s+-\s+(?P<target>.+))?$",
    re.IGNORECASE,
)
_TEST_FAILED_RE = re.compile(r"^\s*Failed\s+(?P<name>.+?)(?:\s+\[[^\]]+\])?\s*$")
_FORMAT_NEEDS_RE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s+"
    r"(?:error|warning)\s+(?P<code>[A-Z]{2,}\d+):\s+(?P<message>.+)$",
    re.IGNORECASE,
)
_FORMAT_DONE_RE = re.compile(
    r"^(?:Formatted(?:\s+code\s+file)?\s+['\"]?(?P<path>.+?)['\"]?\.?|"
    r"Successfully formatted\s+(?P<path2>.+))$",
    re.IGNORECASE,
)


def _compact_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 3:
        return normalized
    return "/".join(parts[-3:])


def _truncate(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _project_count(text: str, default: int = 1) -> int:
    projects = {match.group("project") for match in _PROJECT_RE.finditer(text)}
    return len(projects) or default


def _duration_or_unknown(text: str) -> str:
    match = _TIME_RE.search(text)
    if match:
        return match.group("duration")
    return "unknown"


def _parse_issues(text: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = _ISSUE_RE.match(line)
        if not match:
            continue
        entry = {
            "path": match.group("path") or "",
            "line": match.group("line") or "",
            "col": match.group("col") or "",
            "code": (match.group("code") or "").upper(),
            "message": match.group("message").strip(),
        }
        if match.group("severity").lower() == "error":
            errors.append(entry)
        else:
            warnings.append(entry)
    return errors, warnings


def _format_issue(issue: dict[str, str], severity: str) -> str:
    code = f" {issue['code']}" if issue["code"] else ""
    message = _truncate(issue["message"])
    if not issue["path"]:
        return f"  {severity}{code}: {message}"
    location = _compact_path(issue["path"])
    if issue["line"] and issue["col"]:
        location += f"({issue['line']},{issue['col']})"
    return f"  {location} {severity}{code}: {message}"


def _format_build_like(command: str, text: str, exit_code: int) -> tuple[str, str]:
    subcommand = "restore" if "dotnet restore" in command else "build"
    errors, warnings = _parse_issues(text)
    status = "ok" if exit_code == 0 and not errors else "fail"
    duration = _duration_or_unknown(text)
    projects = _project_count(text)
    label = "restored" if subcommand == "restore" else "projects"
    lines = [
        f"{status} dotnet {subcommand}: {projects} {label}, {len(errors)} errors, {len(warnings)} warnings ({duration})"
    ]
    if errors:
        lines.append("Errors:")
        lines.extend(_format_issue(issue, "error") for issue in errors[:20])
        if len(errors) > 20:
            lines.append(f"  ... +{len(errors) - 20} more errors")
    if warnings:
        lines.append("Warnings:")
        lines.extend(_format_issue(issue, "warning") for issue in warnings[:10])
        if len(warnings) > 10:
            lines.append(f"  ... +{len(warnings) - 10} more warnings")
    return "\n".join(lines), f"dotnet.{subcommand}"


def _format_test(text: str, exit_code: int) -> tuple[str, str]:
    errors, warnings = _parse_issues(text)
    passed = 0
    failed = 0
    skipped = 0
    total = 0
    duration = "unknown"
    targets: set[str] = set()
    failed_tests: list[list[str]] = []
    current_failure: list[str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        summary_match = _TEST_SUMMARY_RE.search(stripped)
        if summary_match:
            passed += int(summary_match.group("passed"))
            failed += int(summary_match.group("failed"))
            skipped += int(summary_match.group("skipped"))
            total += int(summary_match.group("total"))
            duration = summary_match.group("duration").strip()
            target = summary_match.group("target")
            if target:
                targets.add(target.strip())
            if current_failure:
                failed_tests.append(current_failure)
                current_failure = None
            continue
        failure_match = _TEST_FAILED_RE.match(line)
        if failure_match and not stripped.startswith("Failed!"):
            if current_failure:
                failed_tests.append(current_failure)
            current_failure = [failure_match.group("name")]
            continue
        if current_failure is not None:
            if not stripped:
                failed_tests.append(current_failure)
                current_failure = None
            elif not _ISSUE_RE.match(line):
                current_failure.append(_truncate(stripped, 320))

    if current_failure:
        failed_tests.append(current_failure)

    project_count = len(targets) or _project_count(text)
    warning_count = len(warnings)
    has_failures = failed > 0 or bool(failed_tests) or exit_code != 0

    if total == 0 and exit_code == 0 and not errors and not failed_tests:
        return (
            f"ok dotnet test: completed ({warning_count} warnings in {project_count} projects)",
            "dotnet.test",
        )

    if has_failures:
        lines = [
            f"fail dotnet test: {passed} passed, {max(failed, len(failed_tests))} failed, {skipped} skipped, {warning_count} warnings in {project_count} projects ({duration})"
        ]
    else:
        lines = [
            f"ok dotnet test: {passed or total} tests passed, {warning_count} warnings in {project_count} projects ({duration})"
        ]
    if failed_tests:
        lines.append("Failed Tests:")
        for failure in failed_tests[:15]:
            lines.append(f"  {failure[0]}")
            for detail in failure[1:5]:
                lines.append(f"    {detail}")
        if len(failed_tests) > 15:
            lines.append(f"  ... +{len(failed_tests) - 15} more failed tests")
    if errors:
        lines.append("Errors:")
        lines.extend(_format_issue(issue, "error") for issue in errors[:10])
    if warnings:
        lines.append("Warnings:")
        lines.extend(_format_issue(issue, "warning") for issue in warnings[:10])
    return "\n".join(lines), "dotnet.test"


def _format_dotnet_format(text: str, exit_code: int) -> tuple[str, str]:
    changed: list[str] = []
    needs: list[tuple[str, str, str, str]] = []
    already_formatted = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        match = _FORMAT_DONE_RE.match(stripped)
        if match:
            changed.append(match.group("path") or match.group("path2") or stripped)
            continue
        match = _FORMAT_NEEDS_RE.match(stripped)
        if match and (match.group("code") or "").upper().startswith("IDE"):
            needs.append(
                (
                    match.group("path"),
                    match.group("line"),
                    match.group("col"),
                    match.group("code").upper(),
                )
            )
            continue
        lowered = stripped.lower()
        if "already formatted" in lowered:
            number = re.search(r"(\d+)", stripped)
            if number:
                already_formatted = int(number.group(1))

    if changed:
        lines = [f"ok dotnet format: formatted {len(changed)} files"]
        if already_formatted:
            lines[0] += f" ({already_formatted} already formatted)"
        for path in changed[:20]:
            lines.append(f"  {_compact_path(path)}")
        if len(changed) > 20:
            lines.append(f"  ... +{len(changed) - 20} more files")
        return "\n".join(lines), "dotnet.format"

    if needs:
        lines = [f"Format: {len(needs)} files need formatting"]
        for index, (path, line, col, code) in enumerate(needs[:20], start=1):
            lines.append(
                f"{index}. {_compact_path(path)} (line {line}, col {col}, {code})"
            )
        if len(needs) > 20:
            lines.append(f"... +{len(needs) - 20} more files")
        if already_formatted:
            lines.append(f"ok {already_formatted} files already formatted")
        lines.append("Run `dotnet format` to apply fixes")
        return "\n".join(lines), "dotnet.format"

    if exit_code == 0:
        return "ok dotnet format: all files formatted correctly", "dotnet.format"
    return text.strip() or "dotnet format", "dotnet.format"


def filter_dotnet_output(
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
    lowered = command.lower()
    if "dotnet test" in lowered:
        text, filter_name = _format_test(combined, exit_code)
    elif "dotnet restore" in lowered:
        text, filter_name = _format_build_like(command, combined, exit_code)
    elif "dotnet format" in lowered:
        text, filter_name = _format_dotnet_format(combined, exit_code)
    else:
        text, filter_name = _format_build_like(command, combined, exit_code)
    return make_filter_result(
        text or generic.output,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
