from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_GO_PACKAGE_OK_RE = re.compile(r"^ok\s+(\S+)\s+")
_GO_PACKAGE_FAIL_RE = re.compile(r"^FAIL\s+(\S+)(?:\s|$)")
_GO_TEST_FAIL_RE = re.compile(r"^--- FAIL: (\S+)")
_GOLANGCI_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s+"
    r"(?P<message>.+?)"
    r"(?:\s+\((?P<linter1>[^()]+)\)|\s+\[(?P<linter2>[^\]]+)\])$"
)


def _compact_path(path: str) -> str:
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if len(parts) <= 3:
        return path.replace("\\", "/")
    return "/".join(parts[-3:])


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _extract_golangci_json_payload(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None
    candidates = [stripped]
    first_line = stripped.splitlines()[0].strip()
    if first_line != stripped:
        candidates.append(first_line)
    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("Issues"), list):
            return parsed
    return None


def _format_golangci_json(text: str) -> str | None:
    payload = _extract_golangci_json_payload(text)
    if payload is None:
        return None
    raw_issues = payload.get("Issues") or []
    issues = [issue for issue in raw_issues if isinstance(issue, dict)]
    if not issues:
        return "golangci-lint: No issues found"

    by_linter = Counter()
    by_file: dict[str, Counter[str]] = defaultdict(Counter)
    previews: dict[tuple[str, str], str] = {}

    for issue in issues:
        linter = str(issue.get("FromLinter") or "<unknown>")
        pos = issue.get("Pos") if isinstance(issue.get("Pos"), dict) else {}
        path = str(pos.get("Filename") or "<unknown>")
        by_linter[linter] += 1
        by_file[path][linter] += 1
        source_lines = issue.get("SourceLines")
        if isinstance(source_lines, list):
            for source_line in source_lines:
                if isinstance(source_line, str) and source_line.strip():
                    previews.setdefault((path, linter), source_line.strip())
                    break

    lines = [f"golangci-lint: {len(issues)} issues in {len(by_file)} files"]
    lines.append(
        "Top linters: "
        + ", ".join(
            f"{linter} ({count}x)" for linter, count in by_linter.most_common(10)
        )
    )
    for path, linter_counts in sorted(
        by_file.items(), key=lambda item: (-sum(item[1].values()), item[0])
    )[:10]:
        lines.append(f"{_compact_path(path)} ({sum(linter_counts.values())} issues)")
        for linter, count in linter_counts.most_common(3):
            lines.append(f"  {linter} ({count})")
            preview = previews.get((path, linter))
            if preview:
                lines.append(f"    -> {_truncate(preview, 80)}")
    if len(by_file) > 10:
        lines.append(f"... +{len(by_file) - 10} more files")
    return "\n".join(lines)


def _filter_go_test(text: str, exit_code: int) -> str:
    package_passes = 0
    failed_packages: set[str] = set()
    failures: dict[str, list[dict[str, object]]] = defaultdict(list)
    current_failure: dict[str, object] | None = None
    build_errors: dict[str, list[str]] = defaultdict(list)
    current_package = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        ok_match = _GO_PACKAGE_OK_RE.match(stripped)
        if ok_match:
            package_passes += 1
            current_failure = None
            current_package = ok_match.group(1)
            continue
        fail_match = _GO_PACKAGE_FAIL_RE.match(stripped)
        if fail_match:
            current_package = fail_match.group(1)
            failed_packages.add(current_package)
            current_failure = None
            continue
        test_fail_match = _GO_TEST_FAIL_RE.match(stripped)
        if test_fail_match:
            current_failure = {
                "name": test_fail_match.group(1),
                "lines": [],
            }
            failures[current_package or "<unknown>"].append(current_failure)
            continue
        if current_failure is not None:
            lowered = stripped.lower()
            if (
                stripped
                and not stripped.startswith(("=== RUN", "--- FAIL"))
                and (
                    "error" in lowered
                    or "expected" in lowered
                    or "got" in lowered
                    or "panic" in lowered
                    or stripped.startswith(("at ", "\t"))
                    or ".go:" in stripped
                )
            ):
                current_failure["lines"].append(stripped)
            continue
        if (
            stripped
            and ".go:" in stripped
            and (
                "undefined" in stripped.lower()
                or "cannot" in stripped.lower()
                or "error" in stripped.lower()
            )
        ):
            build_errors[current_package or "<build>"].append(stripped)

    if exit_code == 0 and package_passes and not failed_packages:
        return f"Go test: {package_passes} packages passed"
    if not failed_packages and not build_errors:
        return text.strip()

    lines = [
        f"Go test: {package_passes} packages passed, "
        f"{len(failed_packages) or len(build_errors)} packages failed"
    ]
    for package, errors in build_errors.items():
        lines.append(f"{package} [build failed]")
        for error in errors[:5]:
            lines.append(f"  {_truncate(error)}")
    for package, package_failures in failures.items():
        lines.append(f"{package} ({len(package_failures)} failed)")
        for failure in package_failures[:5]:
            lines.append(f"  [FAIL] {failure['name']}")
            for detail in failure["lines"][:3]:
                lines.append(f"     {_truncate(detail, 100)}")
    return "\n".join(lines)


def filter_go_output(
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
    if "go test" in lowered:
        text = _filter_go_test(combined, exit_code)
        filter_name = "go.test"
    elif "go build" in lowered:
        issues = [line.strip() for line in combined.splitlines() if ".go:" in line]
        text = (
            "Go build: success"
            if exit_code == 0 and not issues
            else "Go build:\n"
            + "\n".join(f"  {_truncate(line)}" for line in issues[:20])
        )
        filter_name = "go.build"
    elif "go vet" in lowered:
        issues = [
            line.strip()
            for line in combined.splitlines()
            if line.strip() and ".go:" in line and not line.strip().startswith("#")
        ]
        text = (
            "Go vet: no issues found"
            if exit_code == 0 and not issues
            else "Go vet:\n" + "\n".join(f"  {_truncate(line)}" for line in issues[:20])
        )
        filter_name = "go.vet"
    else:
        text = generic.output
        filter_name = generic.filter_name or "generic"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )


def filter_golangci_output(
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
    json_summary = _format_golangci_json(combined)
    if json_summary is not None:
        return make_filter_result(
            json_summary,
            filter_name="golangci-lint",
            max_output_lines=max_output_lines,
            error=generic.error,
        )
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    linter_counter = Counter()
    for raw_line in combined.splitlines():
        stripped = raw_line.strip()
        match = _GOLANGCI_RE.match(stripped)
        if not match:
            continue
        linter = match.group("linter1") or match.group("linter2") or "<unknown>"
        entry = {
            "linter": linter,
            "line": match.group("line"),
            "message": match.group("message").strip(),
        }
        by_file[match.group("path")].append(entry)
        linter_counter[linter] += 1
    if not by_file:
        text = "golangci-lint: no issues found" if exit_code == 0 else generic.output
        return make_filter_result(
            text,
            filter_name="golangci-lint",
            max_output_lines=max_output_lines,
            error=generic.error,
        )
    lines = [
        f"golangci-lint: {sum(linter_counter.values())} issues in {len(by_file)} files"
    ]
    lines.append(
        "Top linters: "
        + ", ".join(
            f"{linter} ({count}x)" for linter, count in linter_counter.most_common(5)
        )
    )
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for entry in entries[:3]:
            lines.append(
                f"  L{entry['line']}: [{entry['linter']}] {_truncate(entry['message'])}"
            )
    return make_filter_result(
        "\n".join(lines),
        filter_name="golangci-lint",
        max_output_lines=max_output_lines,
        error=generic.error,
    )
