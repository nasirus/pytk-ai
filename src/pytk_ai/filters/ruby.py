from __future__ import annotations

import json
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
_RSPEC_SCREENSHOT_RE = re.compile(r"saved screenshot to (.+)", re.IGNORECASE)
_MINITEST_FAILURE_RE = re.compile(r"^\d+\)\s+(Failure|Error):$")


def _severity_rank(severity: str) -> int:
    return {
        "fatal": 0,
        "error": 0,
        "warning": 1,
        "convention": 2,
        "refactor": 2,
        "info": 2,
    }.get(severity.lower(), 3)


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


def _is_rspec_internal_backtrace(line: str) -> bool:
    return any(
        marker in line
        for marker in ("/gems/", "lib/rspec", "lib/ruby/", "vendor/bundle")
    )


def _parse_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if not stripped or not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _strip_rspec_noise(output: str) -> str:
    lines: list[str] = []
    in_simplecov_block = False
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.lower()
        if "running via spring preloader" in lowered:
            continue
        if stripped.startswith("DEPRECATION WARNING:"):
            continue
        if stripped.startswith("Finished in "):
            continue
        if any(
            token in lowered for token in ("coverage report", "simplecov", "coverage/")
        ):
            in_simplecov_block = True
            continue
        if in_simplecov_block:
            if not stripped:
                in_simplecov_block = False
            continue
        screenshot = _RSPEC_SCREENSHOT_RE.search(stripped)
        if screenshot:
            lines.append(f"[screenshot: {screenshot.group(1).strip()}]")
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def _build_rspec_json_summary(payload: dict[str, object]) -> str | None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    duration = float(summary.get("duration") or 0.0)
    example_count = int(summary.get("example_count") or 0)
    failure_count = int(summary.get("failure_count") or 0)
    pending_count = int(summary.get("pending_count") or 0)
    errors_outside = int(summary.get("errors_outside_of_examples_count") or 0)

    if example_count == 0 and errors_outside == 0:
        return "RSpec: No examples found"
    if example_count == 0 and errors_outside > 0:
        return f"RSpec: {errors_outside} errors outside of examples ({duration:.2f}s)"

    passed = max(example_count - failure_count - pending_count, 0)
    if failure_count == 0 and errors_outside == 0:
        text = f"✓ RSpec: {passed} passed"
        if pending_count:
            text += f", {pending_count} pending"
        return f"{text} ({duration:.2f}s)"

    lines = [f"RSpec: {passed} passed, {failure_count} failed"]
    if pending_count:
        lines[0] += f", {pending_count} pending"
    lines[0] += f" ({duration:.2f}s)"
    examples = payload.get("examples")
    if not isinstance(examples, list):
        return "\n".join(lines)
    failures = [
        example
        for example in examples
        if isinstance(example, dict) and example.get("status") == "failed"
    ]
    for index, example in enumerate(failures[:5], start=1):
        lines.append(
            f"{index}. ❌ {example.get('full_description') or '<failed example>'}"
        )
        file_path = str(example.get("file_path") or "")
        line_number = example.get("line_number") or ""
        if file_path:
            lines.append(f"   {file_path}:{line_number}")
        exception = example.get("exception")
        if isinstance(exception, dict):
            exc_class = str(exception.get("class") or "")
            short_class = exc_class.rsplit("::", 1)[-1] if exc_class else ""
            message = str(exception.get("message") or "").splitlines()[0]
            if short_class or message:
                lines.append(f"   {short_class}: {_truncate(message)}".rstrip(": "))
            backtrace = exception.get("backtrace")
            if isinstance(backtrace, list):
                for entry in backtrace:
                    if isinstance(entry, str) and not _is_rspec_internal_backtrace(
                        entry
                    ):
                        lines.append(f"   {_truncate(entry)}")
                        break
    if len(failures) > 5:
        lines.append(f"... +{len(failures) - 5} more failures")
    return "\n".join(lines)


def _compact_rspec_failure(lines: list[str]) -> str:
    kept: list[str] = []
    spec_file = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ./spec/") or stripped.startswith("# ./test/"):
            spec_file = stripped.removeprefix("# ")
            continue
        if stripped.startswith("#") and _is_rspec_internal_backtrace(stripped):
            continue
        kept.append(stripped)
    if spec_file:
        kept.append(spec_file)
    return "\n   ".join(kept)


def _filter_rspec_text_summary(text: str, exit_code: int, fallback: str) -> str:
    cleaned = _strip_rspec_noise(text)
    failures: list[str] = []
    current: list[str] = []
    summary = ""
    in_failures = False
    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip()
        if stripped == "Failures:":
            in_failures = True
            continue
        if stripped == "Failed examples:":
            if current:
                failures.append(_compact_rspec_failure(current))
                current = []
            in_failures = False
            continue
        if _RSPEC_SUMMARY_RE.search(stripped):
            summary = stripped
            if current:
                failures.append(_compact_rspec_failure(current))
                current = []
            continue
        if in_failures:
            if re.match(r"^\d+\)", stripped):
                if current:
                    failures.append(_compact_rspec_failure(current))
                current = [stripped]
            elif stripped and not _is_rspec_internal_backtrace(stripped):
                current.append(stripped)
    if current:
        failures.append(_compact_rspec_failure(current))
    if not summary and exit_code == 0 and not failures:
        return "RSpec: passed"
    if not failures:
        return f"RSpec: {summary}" if summary else fallback
    lines = [f"RSpec: {summary}" if summary else "RSpec failures"]
    for index, failure in enumerate(failures[:5], start=1):
        lines.append(f"{index}. ❌ {failure}")
    if len(failures) > 5:
        lines.append(f"... +{len(failures) - 5} more failures")
    return "\n".join(lines)


def _parse_minitest_summary(summary: str) -> tuple[int, int, int, int, int]:
    runs = assertions = failures = errors = skips = 0
    for part in summary.split(","):
        words = part.strip().split()
        if len(words) < 2:
            continue
        try:
            count = int(words[0])
        except ValueError:
            continue
        label = words[1].rstrip(",")
        if label in {"runs", "run", "tests", "test"}:
            runs = count
        elif label in {"assertions", "assertion"}:
            assertions = count
        elif label in {"failures", "failure"}:
            failures = count
        elif label in {"errors", "error"}:
            errors = count
        elif label in {"skips", "skip"}:
            skips = count
    return runs, assertions, failures, errors, skips


def _build_minitest_summary(summary: str, failures: list[str]) -> str:
    runs, _assertions, fail_count, error_count, skips = _parse_minitest_summary(summary)
    if runs == 0 and not summary:
        return "rake test: no tests ran"
    if fail_count == 0 and error_count == 0:
        text = f"ok rake test: {runs} runs, 0 failures"
        if skips:
            text += f", {skips} skips"
        return text
    lines = [f"rake test: {runs} runs, {fail_count} failures, {error_count} errors"]
    if skips:
        lines[0] += f", {skips} skips"
    if not failures:
        return lines[0]
    lines.append("")
    for index, failure in enumerate(failures[:10], start=1):
        failure_lines = failure.splitlines()
        if not failure_lines:
            continue
        lines.append(f"{index}. {failure_lines[0].strip()}")
        for detail in failure_lines[1:5]:
            if detail.strip():
                lines.append(f"   {_truncate(detail.strip())}")
        if index < min(len(failures), 10):
            lines.append("")
    if len(failures) > 10:
        lines.append(f"... +{len(failures) - 10} more failures")
    return "\n".join(lines).strip()


def _filter_minitest_output(text: str) -> str:
    clean = text.replace("\r", "\n")
    failures: list[str] = []
    current: list[str] = []
    summary_line = ""
    in_failures = False
    for raw_line in clean.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if (
            " runs," in stripped or " tests," in stripped
        ) and " assertions," in stripped:
            summary_line = stripped
            continue
        if stripped == "# Running:" or stripped.startswith("Started with run options"):
            in_failures = False
            continue
        if stripped.startswith("Finished in "):
            in_failures = True
            continue
        if not in_failures:
            continue
        if _MINITEST_FAILURE_RE.match(stripped):
            if current:
                failures.append("\n".join(current))
            current = [stripped]
            continue
        if not stripped:
            if current:
                failures.append("\n".join(current))
                current = []
            continue
        if current:
            current.append(line)
    if current:
        failures.append("\n".join(current))
    return _build_minitest_summary(summary_line, failures)


def filter_rubocop_output(
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
    payload = _parse_json_object(combined)
    if payload is not None and isinstance(payload.get("summary"), dict):
        summary = payload["summary"]
        offense_count = int(summary.get("offense_count") or 0)
        inspected_count = int(summary.get("inspected_file_count") or 0)
        files = payload.get("files") if isinstance(payload.get("files"), list) else []
        if offense_count == 0:
            return make_filter_result(
                f"ok ✓ rubocop ({inspected_count} files)",
                filter_name="rubocop",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        correctable_count = int(summary.get("correctable_offense_count") or 0)
        if not correctable_count:
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                for offense in file_info.get("offenses") or []:
                    if isinstance(offense, dict) and offense.get("correctable"):
                        correctable_count += 1
        files_with_offenses: list[tuple[str, list[dict[str, object]]]] = []
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            offenses = [
                offense
                for offense in file_info.get("offenses") or []
                if isinstance(offense, dict)
            ]
            if offenses:
                files_with_offenses.append(
                    (str(file_info.get("path") or "<unknown>"), offenses)
                )
        files_with_offenses.sort(
            key=lambda item: (
                min(
                    _severity_rank(str(offense.get("severity") or ""))
                    for offense in item[1]
                ),
                item[0],
            )
        )
        lines = [f"rubocop: {offense_count} offenses ({inspected_count} files)"]
        for path, offenses in files_with_offenses[:10]:
            lines.append(_compact_path(path))
            offenses.sort(
                key=lambda offense: (
                    _severity_rank(str(offense.get("severity") or "")),
                    int((offense.get("location") or {}).get("start_line") or 0),
                )
            )
            for offense in offenses[:5]:
                location = (
                    offense.get("location")
                    if isinstance(offense.get("location"), dict)
                    else {}
                )
                line = int(location.get("start_line") or 0)
                message = str(offense.get("message") or "").splitlines()[0]
                lines.append(
                    f"  :{line} {offense.get('cop_name') or '<unknown>'} -- {_truncate(message)}"
                )
            if len(offenses) > 5:
                lines.append(f"  ... +{len(offenses) - 5} more")
        if len(files_with_offenses) > 10:
            lines.append(f"... +{len(files_with_offenses) - 10} more files")
        if correctable_count:
            lines.append(f"({correctable_count} correctable, run `rubocop -A`)")
        return make_filter_result(
            "\n".join(lines),
            filter_name="rubocop",
            max_output_lines=max_output_lines,
            error=generic.error,
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
                text = f"ok ✓ rubocop ({stripped.split()[0]} files)"
                break
            if "inspected" in stripped and "autocorrected" in stripped:
                parts = [part.strip() for part in stripped.split(",")]
                files = parts[0].split()[0] if parts else "0"
                corrected = "0"
                for part in reversed(parts):
                    if "autocorrected" in part:
                        corrected = part.split()[0]
                        break
                text = f"ok ✓ rubocop -A ({files} files, {corrected} autocorrected)"
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
    combined = _combine_streams(stdout, stderr, exit_code)
    generic = filter_generic_output(
        command,
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    payload = _parse_json_object(combined) or _parse_json_object(
        _strip_rspec_noise(combined)
    )
    if payload is not None:
        text = _build_rspec_json_summary(payload)
        if text is not None:
            return make_filter_result(
                text,
                filter_name="rspec",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
    lines = _filter_rspec_text_summary(combined, exit_code, generic.output)
    return make_filter_result(
        lines,
        filter_name="rspec",
        max_output_lines=max_output_lines,
        error=generic.error,
    )


def filter_rake_output(
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
    return make_filter_result(
        _filter_minitest_output(combined),
        filter_name="rake",
        max_output_lines=max_output_lines,
        error=generic.error,
    )
