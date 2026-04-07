from __future__ import annotations

import json
import re
import shlex

from ..models import FilterResult
from ..plan.normalize import infer_filter_hint, strip_env_prefix
from .build import _format_cargo_summary
from .base import make_filter_result, strip_ansi
from .generic import _combine_streams
from .go import filter_go_output
from .python import filter_python_output
from .ruby import filter_rake_output, filter_rspec_output


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
    re.compile(r"^---- .+ ----$"),
    re.compile(r"^thread '.*' panicked at "),
    re.compile(r"^assertion `.*` failed"),
    re.compile(r"^\s*at .+:\d+:\d+"),
    re.compile(r"^\s+[A-Za-z0-9_:/.-]+$"),
)
_CARGO_RESULT_RE = re.compile(
    r"^test result:\s+"
    r"(?P<status>ok|FAILED)\.\s+"
    r"(?P<passed>\d+)\s+passed;\s+"
    r"(?P<failed>\d+)\s+failed;\s+"
    r"(?P<ignored>\d+)\s+ignored;\s+"
    r"(?P<measured>\d+)\s+measured;\s+"
    r"(?P<filtered>\d+)\s+filtered out"
    r"(?:;\s+finished in\s+(?P<duration>.+))?$",
    re.IGNORECASE,
)
_PLAYWRIGHT_SUMMARY_RE = re.compile(r"(\d+)\s+(passed|failed|flaky|skipped)")
_PLAYWRIGHT_DURATION_RE = re.compile(r"\((\d+(?:\.\d+)?)(ms|s|m)\)")
_PLAYWRIGHT_FAILURE_RE = re.compile(r"^[×✗]\s+(.+)$")
_VITEST_TESTS_RE = re.compile(
    r"Tests\s+(?:(\d+)\s+failed\s+\|\s+)?(\d+)\s+passed(?:\s+\|\s+(\d+)\s+skipped)?",
    re.IGNORECASE,
)
_VITEST_DURATION_RE = re.compile(r"Duration\s+([\d.]+)(ms|s)", re.IGNORECASE)


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                continue
            if char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        start = text.find("{", start + 1)
    return None


def _duration_ms(value: str, unit: str) -> int:
    number = float(value)
    if unit == "ms":
        return int(number)
    if unit == "s":
        return int(number * 1000.0)
    if unit == "m":
        return int(number * 60000.0)
    return int(number)


def _compact_error_message(message: str) -> str:
    cleaned = strip_ansi(message).replace("\r", "\n")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines[:6])


def _format_test_result_summary(
    *,
    passed: int,
    failed: int,
    skipped: int,
    duration_ms: int | None,
    failures: list[tuple[str, str]],
    filter_name: str,
) -> str:
    lines = [f"PASS ({passed}) FAIL ({failed})"]
    if failures:
        lines.append("")
        for index, (name, message) in enumerate(failures[:5], start=1):
            lines.append(f"{index}. {name}")
            for detail in message.splitlines() or [message]:
                if detail:
                    lines.append(f"   {detail}")
        if len(failures) > 5:
            lines.append("")
            lines.append(f"... +{len(failures) - 5} more failures")
    if duration_ms is not None:
        lines.append("")
        lines.append(f"Time: {duration_ms}ms")
    return make_filter_result(
        "\n".join(lines),
        filter_name=filter_name,
        max_output_lines=200,
    ).output


def _collect_playwright_failures(
    suites: list[dict[str, object]], failures: list[tuple[str, str]]
) -> None:
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        for spec in suite.get("specs") or []:
            if not isinstance(spec, dict) or spec.get("ok") is True:
                continue
            test_name = str(spec.get("title") or "<failed test>")
            error_message = "Test failed"
            for test in spec.get("tests") or []:
                if not isinstance(test, dict) or test.get("status") != "unexpected":
                    continue
                for result in test.get("results") or []:
                    if not isinstance(result, dict):
                        continue
                    if result.get("status") not in {
                        "failed",
                        "timedOut",
                        "interrupted",
                    }:
                        continue
                    errors = result.get("errors") or []
                    if errors and isinstance(errors[0], dict):
                        error_message = _compact_error_message(
                            str(errors[0].get("message") or "Test failed")
                        )
                    break
                if error_message != "Test failed":
                    break
            failures.append((test_name, error_message))
        nested = suite.get("suites") or []
        if isinstance(nested, list):
            _collect_playwright_failures(nested, failures)


def _filter_playwright_output(text: str, *, max_output_lines: int) -> str:
    raw = _extract_json_object(text)
    if raw is not None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            stats = (
                payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
            )
            failures: list[tuple[str, str]] = []
            suites = (
                payload.get("suites") if isinstance(payload.get("suites"), list) else []
            )
            _collect_playwright_failures(suites, failures)
            return _format_test_result_summary(
                passed=int(stats.get("expected") or 0),
                failed=int(stats.get("unexpected") or 0),
                skipped=int(stats.get("skipped") or 0),
                duration_ms=int(float(stats.get("duration") or 0.0))
                if stats.get("duration") is not None
                else None,
                failures=failures,
                filter_name="playwright",
            )

    clean = strip_ansi(text)
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for match in _PLAYWRIGHT_SUMMARY_RE.finditer(clean):
        status = match.group(2)
        if status in counts:
            counts[status] = int(match.group(1))
    duration_match = _PLAYWRIGHT_DURATION_RE.search(clean)
    duration = (
        _duration_ms(duration_match.group(1), duration_match.group(2))
        if duration_match is not None
        else None
    )
    failures: list[tuple[str, str]] = []
    lines = clean.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = _PLAYWRIGHT_FAILURE_RE.match(stripped)
        if match is None:
            continue
        details: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor].rstrip()
            if not candidate.strip():
                if details:
                    break
                cursor += 1
                continue
            if _PLAYWRIGHT_FAILURE_RE.match(candidate.strip()):
                break
            if candidate.startswith(("  ", "    ")) or details:
                details.append(candidate.strip())
                cursor += 1
                continue
            break
        failures.append((match.group(1), _compact_error_message("\n".join(details))))
    if counts["passed"] or counts["failed"] or counts["skipped"]:
        return _format_test_result_summary(
            passed=counts["passed"],
            failed=counts["failed"],
            skipped=counts["skipped"],
            duration_ms=duration,
            failures=failures,
            filter_name="playwright",
        )
    return make_filter_result(
        _generic_test_summary(clean),
        filter_name="playwright",
        max_output_lines=max_output_lines,
    ).output


def _filter_vitest_output(text: str, *, max_output_lines: int) -> str:
    raw = _extract_json_object(text)
    if raw is not None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            failures: list[tuple[str, str]] = []
            for file_result in payload.get("testResults") or []:
                if not isinstance(file_result, dict):
                    continue
                for assertion in file_result.get("assertionResults") or []:
                    if (
                        not isinstance(assertion, dict)
                        or assertion.get("status") != "failed"
                    ):
                        continue
                    failures.append(
                        (
                            str(assertion.get("fullName") or "<failed test>"),
                            _compact_error_message(
                                "\n".join(assertion.get("failureMessages") or [])
                            ),
                        )
                    )
            start = payload.get("startTime")
            end = payload.get("endTime")
            duration = None
            if isinstance(start, int) and isinstance(end, int):
                duration = max(end - start, 0)
            return _format_test_result_summary(
                passed=int(payload.get("numPassedTests") or 0),
                failed=int(payload.get("numFailedTests") or 0),
                skipped=int(payload.get("numPendingTests") or 0),
                duration_ms=duration,
                failures=failures,
                filter_name="vitest",
            )

    clean = strip_ansi(text)
    tests_match = _VITEST_TESTS_RE.search(clean)
    duration_match = _VITEST_DURATION_RE.search(clean)
    failures: list[tuple[str, str]] = []
    lines = clean.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if "[x]" not in stripped and not stripped.startswith("FAIL"):
            index += 1
            continue
        details: list[str] = []
        index += 1
        while index < len(lines):
            candidate = lines[index].rstrip()
            if not candidate.strip():
                if details:
                    break
                index += 1
                continue
            if candidate.startswith("  "):
                details.append(candidate.strip())
                index += 1
                continue
            break
        failures.append((stripped, _compact_error_message("\n".join(details))))
    if tests_match is not None:
        failed = int(tests_match.group(1) or 0)
        passed = int(tests_match.group(2) or 0)
        skipped = int(tests_match.group(3) or 0)
        duration = (
            _duration_ms(duration_match.group(1), duration_match.group(2))
            if duration_match is not None
            else None
        )
        return _format_test_result_summary(
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_ms=duration,
            failures=failures,
            filter_name="vitest",
        )
    return make_filter_result(
        _generic_test_summary(clean),
        filter_name="vitest",
        max_output_lines=max_output_lines,
    ).output


def _format_aggregated_cargo_results(summary_lines: list[str]) -> str | None:
    if not summary_lines:
        return None

    suites = 0
    passed = 0
    failed = 0
    ignored = 0
    measured = 0
    filtered = 0

    for line in summary_lines:
        match = _CARGO_RESULT_RE.match(line.strip())
        if match is None:
            return None
        suites += 1
        passed += int(match.group("passed"))
        failed += int(match.group("failed"))
        ignored += int(match.group("ignored"))
        measured += int(match.group("measured"))
        filtered += int(match.group("filtered"))

    status = "FAILED" if failed else "ok"
    counts = [f"{passed} passed", f"{failed} failed"]
    if ignored:
        counts.append(f"{ignored} ignored")
    if measured:
        counts.append(f"{measured} measured")
    if filtered:
        counts.append(f"{filtered} filtered out")
    return f"cargo test: {status} ({suites} suites, {'; '.join(counts)})"


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
    result_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("test result:")
    ]
    summary = _generic_test_summary(text)
    if "failures:" in summary:
        if result_lines:
            return "\n".join(summary.splitlines() + result_lines[-1:])
        return summary

    aggregated = _format_aggregated_cargo_results(result_lines)
    if aggregated is not None:
        return aggregated

    if result_lines:
        if summary:
            return "\n".join(summary.splitlines() + result_lines[-1:])
        return result_lines[-1]

    has_compile_errors = any(
        line.lstrip().startswith(("error[", "error:")) for line in text.splitlines()
    )
    if has_compile_errors:
        build_summary, _ = _format_cargo_summary("cargo build", text, 101)
        if build_summary.startswith("cargo build:"):
            return build_summary.replace("cargo build:", "cargo test:", 1)
        return build_summary
    return summary


def _unwrap_test_command(command: str) -> str:
    _, stripped = strip_env_prefix(command.strip())
    try:
        tokens = shlex.split(stripped)
    except ValueError:
        tokens = []
    if tokens[:2] == ["pytk-ai", "test"]:
        return " ".join(tokens[2:]).strip()
    if stripped == "pytk-ai test":
        return ""
    if stripped.startswith("pytk-ai test "):
        return stripped[len("pytk-ai test ") :].strip()
    return stripped


def filter_test_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    inner_command = _unwrap_test_command(command)
    filter_hint = infer_filter_hint(inner_command) if inner_command else None
    if filter_hint == "pytest":
        return filter_python_output(
            inner_command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )
    if filter_hint == "go":
        return filter_go_output(
            inner_command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )
    if filter_hint == "rspec":
        return filter_rspec_output(
            inner_command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )
    if filter_hint == "rake":
        return filter_rake_output(
            inner_command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )

    combined = _combine_streams(stdout, stderr, exit_code)
    lowered = inner_command.lower()
    if "cargo test" in lowered:
        text = _filter_cargo_test(combined)
        filter_name = "test.cargo"
    elif "playwright" in lowered:
        text = _filter_playwright_output(combined, max_output_lines=max_output_lines)
        filter_name = "playwright"
    elif "vitest" in lowered or filter_hint == "vitest":
        text = _filter_vitest_output(combined, max_output_lines=max_output_lines)
        filter_name = "vitest"
    else:
        text = _generic_test_summary(combined)
        filter_name = "test.generic"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
    )
