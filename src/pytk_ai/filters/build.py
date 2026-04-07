from __future__ import annotations

import re
from collections import Counter, defaultdict

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_CARGO_DIAG_RE = re.compile(
    r"^(?P<severity>error|warning)(?:\[(?P<code>[A-Z0-9-]+)\])?:\s*(?P<message>.*)$"
)
_CARGO_LOCATION_RE = re.compile(r"^\s*-->\s+(?P<path>.+?):(?P<line>\d+):\d+")
_ESLINT_STYLISH_RE = re.compile(
    r"^\s*(?P<line>\d+):(?P<col>\d+)\s+"
    r"(?P<severity>error|warning)\s+"
    r"(?P<message>.+?)"
    r"(?:\s{2,}(?P<rule>[A-Za-z0-9@/_-]+))?\s*$"
)
_BIOME_DIAG_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+)\s+"
    r"(?P<severity>error|warning)\s+"
    r"(?:lint/(?P<rule>[A-Za-z0-9/_-]+)\s+)?"
    r"(?P<message>.+)$"
)
_BIOME_BLOCK_HEADER_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+)\s+"
    r"(?P<rule>lint/[A-Za-z0-9/_-]+)\b.*$"
)
_BIOME_NOISE_RE = re.compile(
    r"^(?:\s*$|Checked\s+\d+\s+file|Fixed\s+\d+\s+file|The following command|Run it with)",
    re.IGNORECASE,
)
_TSC_RE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s+"
    r"(?P<severity>error|warning)\s+"
    r"(?P<code>TS\d+):\s+(?P<message>.+)$"
)
_NEXT_ROUTE_RE = re.compile(
    r"^[\s|├└┌]*[○●◐λƒ]\s+(?P<route>/\S*)\s+"
    r"(?P<size>\d+(?:\.\d+)?)\s*(?P<size_unit>kB|B)\s+"
    r"(?P<first>\d+(?:\.\d+)?)\s*(?P<first_unit>kB|B)"
)
_NEXT_TIME_RE = re.compile(r"(?P<time>\d+(?:\.\d+)?\s*(?:ms|s))")
_CARGO_NEXTEST_SUMMARY_RE = re.compile(
    r"Summary\s+\[\s*(?P<duration>[\d.]+)s\]\s+\d+\s+tests?\s+run:\s+"
    r"(?P<passed>\d+)\s+passed(?:,\s+(?P<failed>\d+)\s+failed)?"
    r"(?:,\s+(?P<skipped>\d+)\s+skipped)?",
    re.IGNORECASE,
)
_CARGO_NEXTEST_START_RE = re.compile(
    r"Starting\s+\d+\s+tests?\s+across\s+(?P<binaries>\d+)\s+binar(?:y|ies)",
    re.IGNORECASE,
)
_CARGO_CLIPPY_RULE_RE = re.compile(r"\[(?P<rule>[^\]]+)\]\s*$")
_CARGO_CLIPPY_HELP_RE = re.compile(r"#(?P<rule>[a-z0-9_]+)\s*$", re.IGNORECASE)


def _compact_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 3:
        return normalized
    return "/".join(parts[-3:])


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _parse_cargo_diagnostics(text: str) -> tuple[list[dict[str, str]], int, str | None]:
    diagnostics: list[dict[str, str]] = []
    compiled = 0
    finished_line: str | None = None
    current: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith(("Compiling ", "Checking ")):
            compiled += 1
            continue
        if stripped.startswith(("Downloading ", "Downloaded ", "Blocking waiting")):
            continue
        if stripped.startswith("Finished "):
            finished_line = stripped
            continue
        match = _CARGO_DIAG_RE.match(line)
        if match:
            if match.group("severity") == "warning" and "generated" in stripped:
                continue
            if match.group("severity") == "error" and any(
                phrase in stripped
                for phrase in ("could not compile", "aborting due to")
            ):
                continue
            if current is not None:
                diagnostics.append(current)
            current = {
                "severity": match.group("severity"),
                "code": match.group("code") or "",
                "message": match.group("message").strip(),
                "path": "",
                "line": "",
                "context": "",
            }
            continue
        if current is None:
            continue
        location = _CARGO_LOCATION_RE.match(line)
        if location:
            current["path"] = location.group("path")
            current["line"] = location.group("line")
            continue
        if stripped.startswith(("=", "|")):
            continue
        if stripped.startswith(("help:", "note:")):
            current["context"] = stripped
            continue
        if stripped and not current["context"] and not stripped.startswith("^"):
            current["context"] = stripped

    if current is not None:
        diagnostics.append(current)
    return diagnostics, compiled, finished_line


def _format_cargo_clippy_summary(text: str) -> tuple[str, str]:
    compiled = 0
    warning_groups: dict[str, list[str]] = defaultdict(list)
    error_details: list[str] = []
    warnings = 0
    errors = 0
    current_rule = ""
    current_is_error = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith(
            (
                "Compiling ",
                "Checking ",
                "Downloading ",
                "Downloaded ",
                "Finished ",
            )
        ):
            if stripped.startswith(("Compiling ", "Checking ")):
                compiled += 1
            continue
        if stripped.startswith(("warning:", "warning[", "error:", "error[")):
            if "generated" in stripped and "warning" in stripped:
                continue
            if "aborting due to" in stripped or "could not compile" in stripped:
                continue
            current_is_error = stripped.startswith(("error:", "error["))
            rule_match = _CARGO_CLIPPY_RULE_RE.search(stripped)
            if rule_match:
                current_rule = rule_match.group("rule")
            else:
                prefix = "error: " if current_is_error else "warning: "
                current_rule = stripped.removeprefix(prefix).strip()
            if current_is_error:
                errors += 1
                error_details.append(_truncate(stripped, 160))
            else:
                warnings += 1
            continue
        if stripped.startswith("-->") and current_rule:
            location = stripped.removeprefix("-->").strip()
            if current_is_error:
                error_details.append(_truncate(location, 160))
            else:
                warning_groups[current_rule].append(location)
            continue
        if stripped.startswith("= help:") and not current_is_error and current_rule:
            help_match = _CARGO_CLIPPY_HELP_RE.search(stripped)
            if help_match and not current_rule.startswith("clippy::"):
                rule = f"clippy::{help_match.group('rule')}"
                warning_groups.setdefault(rule, warning_groups.pop(current_rule, []))
                current_rule = rule

    if errors == 0 and warnings == 0:
        summary = "cargo clippy: No issues found"
        if compiled:
            summary += f" ({compiled} crates)"
        return summary, "cargo.clippy"

    lines = [f"cargo clippy: {errors} errors, {warnings} warnings"]
    if compiled:
        lines[0] += f" ({compiled} crates)"
    if error_details:
        lines.append("Error details:")
        for detail in error_details[:5]:
            lines.append(f"  {detail}")
        if len(error_details) > 5:
            lines.append(f"  ... +{len(error_details) - 5} more errors")
    if warning_groups:
        items = sorted(
            warning_groups.items(), key=lambda item: (-len(item[1]), item[0])
        )
        for rule, locations in items[:15]:
            lines.append(f"  {rule} ({len(locations)}x)")
            for location in locations[:3]:
                lines.append(f"    {location}")
            if len(locations) > 3:
                lines.append(f"    ... +{len(locations) - 3} more")
        if len(items) > 15:
            lines.append(f"... +{len(items) - 15} more rules")
    return "\n".join(lines), "cargo.clippy"


def _format_cargo_summary(command: str, text: str, exit_code: int) -> tuple[str, str]:
    lowered = command.lower()
    if "cargo clippy" in lowered:
        return _format_cargo_clippy_summary(text)
    if "cargo nextest" in lowered:
        failures: list[str] = []
        current_header = ""
        current_body: list[str] = []
        summary_line = ""
        binaries = 0
        in_failure = False
        past_summary = False
        cancelled = False

        def flush_failure() -> None:
            nonlocal current_header, current_body
            if not current_header:
                return
            block = current_header
            if current_body:
                block += "\n" + "\n".join(current_body)
            failures.append(block)
            current_header = ""
            current_body = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped.startswith(
                (
                    "Compiling ",
                    "Downloading ",
                    "Downloaded ",
                    "Finished ",
                    "Locking ",
                    "Updating ",
                )
            ):
                continue
            if stripped.startswith("────"):
                continue
            if past_summary:
                continue
            starting_match = _CARGO_NEXTEST_START_RE.match(stripped)
            if starting_match:
                binaries = int(starting_match.group("binaries"))
                continue
            if stripped.startswith("PASS"):
                if in_failure:
                    flush_failure()
                    in_failure = False
                continue
            if stripped.startswith("FAIL"):
                if in_failure:
                    flush_failure()
                current_header = stripped
                current_body = []
                in_failure = True
                continue
            if stripped.startswith(("Cancelling", "Canceling")):
                cancelled = True
                continue
            if stripped.startswith("Nextest run ID"):
                continue
            if stripped.startswith("Summary"):
                summary_line = stripped
                if in_failure:
                    flush_failure()
                    in_failure = False
                past_summary = True
                continue
            if in_failure:
                current_body.append(line)

        if in_failure:
            flush_failure()

        summary_match = _CARGO_NEXTEST_SUMMARY_RE.search(summary_line)
        if summary_match:
            passed = int(summary_match.group("passed"))
            failed = int(summary_match.group("failed") or 0)
            skipped = int(summary_match.group("skipped") or 0)
            duration = summary_match.group("duration")
            meta_parts: list[str] = []
            if binaries == 1:
                meta_parts.append("1 binary")
            elif binaries > 1:
                meta_parts.append(f"{binaries} binaries")
            meta_parts.append(f"{duration}s")
            summary = (
                f"cargo nextest: "
                f"{', '.join(part for part in [f'{passed} passed', f'{failed} failed' if failed else '', f'{skipped} skipped' if skipped else ''] if part)} "
                f"({', '.join(meta_parts)})"
            )
            if failed == 0:
                return summary, "cargo.nextest"
            lines = [*failures]
            if cancelled:
                lines.append("Cancelling due to test failure")
            lines.append(summary)
            return "\n".join(line for line in lines if line), "cargo.nextest"

        if failures:
            lines = [*failures]
            if summary_line:
                lines.append(summary_line)
            return "\n".join(lines), "cargo.nextest"

        return text.strip() or "cargo nextest", "cargo.nextest"

    if "cargo install" in lowered:
        compiled = 0
        installed_crate = ""
        installed_version = ""
        notes: list[str] = []
        errors: list[str] = []
        current_error: list[str] = []
        already_installed = ""

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                if current_error:
                    errors.append("\n".join(current_error))
                    current_error = []
                continue
            if stripped.startswith("Compiling "):
                compiled += 1
                if current_error:
                    current_error.append(line)
                continue
            if stripped.startswith(
                (
                    "Downloading ",
                    "Downloaded ",
                    "Locking ",
                    "Updating ",
                    "Adding ",
                    "Finished ",
                    "Blocking waiting for file lock",
                )
            ):
                continue
            if stripped.startswith("Installing "):
                rest = stripped.removeprefix("Installing ").strip()
                if rest and not rest.startswith("/"):
                    parts = rest.split(maxsplit=1)
                    installed_crate = parts[0]
                    installed_version = parts[1] if len(parts) > 1 else ""
                continue
            if stripped.startswith("Installed ") and not installed_crate:
                rest = stripped.removeprefix("Installed ").strip()
                parts = rest.split(maxsplit=2)
                if parts:
                    installed_crate = parts[0]
                if len(parts) > 1:
                    installed_version = parts[1]
                continue
            if stripped.startswith("Ignored package"):
                marker = stripped.split("`")
                already_installed = marker[1] if len(marker) >= 3 else stripped
                continue
            if stripped.startswith(("Replacing", "Replaced")):
                notes.append(stripped)
                continue
            if stripped.startswith("warning:") and not (
                "generated" in stripped and "warning" in stripped
            ):
                notes.append(stripped)
                continue
            if stripped.startswith(("error[", "error:")) and not any(
                phrase in stripped
                for phrase in ("aborting due to", "could not compile")
            ):
                if current_error:
                    errors.append("\n".join(current_error))
                current_error = [line]
                continue
            if current_error:
                current_error.append(line)

        if current_error:
            errors.append("\n".join(current_error))

        if already_installed:
            return (
                f"cargo install: {already_installed} already installed",
                "cargo.install",
            )

        crate_info = installed_crate or "package"
        if installed_version:
            crate_info = f"{crate_info} {installed_version}"

        if errors:
            header = f"cargo install: {len(errors)} errors ({crate_info}"
            if compiled:
                header += f", {compiled} deps compiled"
            header += ")"
            return "\n".join([header, *errors[:15]]), "cargo.install"

        summary = f"cargo install ({crate_info}"
        if compiled:
            summary += f", {compiled} deps compiled"
        summary += ")"
        if notes:
            return "\n".join([summary, *notes[:8]]), "cargo.install"
        return summary, "cargo.install"

    if "cargo fmt" in lowered:
        files: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if "Would reformat:" in stripped:
                files.append(stripped.split("Would reformat:", 1)[1].strip())
            elif stripped.startswith("Diff in "):
                files.append(stripped.split("Diff in ", 1)[1].split(" at line", 1)[0])
        if not files and exit_code == 0:
            return "cargo fmt: all files formatted", "cargo.fmt"
        if files:
            lines = [f"cargo fmt: {len(files)} files need formatting"]
            for path in files[:10]:
                lines.append(f"  {_compact_path(path)}")
            if len(files) > 10:
                lines.append(f"... +{len(files) - 10} more files")
            return "\n".join(lines), "cargo.fmt"
        return text.strip() or "cargo fmt", "cargo.fmt"

    diagnostics, compiled, finished_line = _parse_cargo_diagnostics(text)
    errors = [diag for diag in diagnostics if diag["severity"] == "error"]
    warnings = [diag for diag in diagnostics if diag["severity"] == "warning"]
    subcommand = "build"
    filter_name = f"cargo.{subcommand}"

    if not diagnostics and exit_code == 0:
        summary = f"cargo {subcommand}: ok"
        if compiled:
            summary += f" ({compiled} crates)"
        if finished_line:
            summary += f"\n{finished_line}"
        return summary, filter_name

    if not diagnostics:
        return text.strip(), filter_name

    code_counter = Counter(diag["code"] for diag in diagnostics if diag["code"])
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for diag in diagnostics:
        by_file[diag["path"] or "<unknown>"].append(diag)

    lines = [
        f"cargo {subcommand}: {len(errors)} errors, {len(warnings)} warnings",
    ]
    if compiled:
        lines[0] += f" ({compiled} crates)"
    if code_counter:
        top_codes = ", ".join(
            f"{code} ({count}x)" for code, count in code_counter.most_common(5)
        )
        lines.append(f"Top codes: {top_codes}")
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for diag in entries[:4]:
            location = f"L{diag['line']}: " if diag["line"] else ""
            code = f"[{diag['code']}] " if diag["code"] else ""
            lines.append(f"  {location}{code}{_truncate(diag['message'])}")
            if diag["context"]:
                lines.append(f"    {_truncate(diag['context'])}")
    if len(by_file) > 8:
        lines.append(f"... +{len(by_file) - 8} more files")
    return "\n".join(lines), filter_name


def _format_stylish_lint(tool: str, text: str) -> str | None:
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    current_file: str | None = None
    errors = 0
    warnings = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if not line.startswith((" ", "\t")) and (
            "/" in stripped
            or stripped.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))
        ):
            current_file = stripped
            continue
        if current_file is None:
            continue
        match = _ESLINT_STYLISH_RE.match(line)
        if not match:
            continue
        entry = {
            "rule": match.group("rule") or "<unknown>",
            "message": match.group("message").strip(),
            "line": match.group("line"),
            "severity": match.group("severity"),
        }
        by_file[current_file].append(entry)
        if entry["severity"] == "error":
            errors += 1
        else:
            warnings += 1

    if not by_file:
        return None

    rule_counter = Counter(
        entry["rule"]
        for entries in by_file.values()
        for entry in entries
        if entry["rule"]
    )
    lines = [f"{tool}: {errors} errors, {warnings} warnings in {len(by_file)} files"]
    if rule_counter:
        lines.append(
            "Top rules: "
            + ", ".join(
                f"{rule} ({count}x)" for rule, count in rule_counter.most_common(5)
            )
        )
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for entry in entries[:3]:
            lines.append(
                f"  L{entry['line']}: [{entry['rule']}] {_truncate(entry['message'])}"
            )
    if len(by_file) > 8:
        lines.append(f"... +{len(by_file) - 8} more files")
    return "\n".join(lines)


def _format_biome(text: str) -> str | None:
    cleaned_lines = [
        raw_line.strip()
        for raw_line in text.splitlines()
        if not _BIOME_NOISE_RE.match(raw_line.strip())
    ]
    cleaned = "\n".join(line for line in cleaned_lines if line).strip()
    if not cleaned:
        return "biome: ok"

    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    severity_counter = Counter()
    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip()
        match = _BIOME_DIAG_RE.match(stripped)
        if not match:
            continue
        entry = {
            "rule": match.group("rule") or "<unknown>",
            "message": match.group("message").strip(),
            "line": match.group("line"),
            "severity": match.group("severity"),
        }
        by_file[match.group("path")].append(entry)
        severity_counter[entry["severity"]] += 1
    if not by_file:
        if any(_BIOME_BLOCK_HEADER_RE.match(line) for line in cleaned.splitlines()):
            return cleaned
        lowered = cleaned.lower()
        if lowered.startswith("found ") and " error" in lowered:
            return cleaned
        return None
    rule_counter = Counter(
        entry["rule"]
        for entries in by_file.values()
        for entry in entries
        if entry["rule"]
    )
    lines = [
        "Biome: "
        f"{severity_counter['error']} errors, {severity_counter['warning']} warnings "
        f"in {len(by_file)} files"
    ]
    if rule_counter:
        lines.append(
            "Top rules: "
            + ", ".join(
                f"{rule} ({count}x)" for rule, count in rule_counter.most_common(5)
            )
        )
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    )[:8]:
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for entry in entries[:3]:
            lines.append(
                f"  L{entry['line']}: [{entry['rule']}] {_truncate(entry['message'])}"
            )
    return "\n".join(lines)


def filter_lint_output(
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
    if "biome" in lowered:
        text = _format_biome(combined) or generic.output
        filter_name = "lint.biome"
    else:
        text = _format_stylish_lint("ESLint", combined) or generic.output
        filter_name = "lint.eslint"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )


def filter_tsc_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    del command
    combined = _combine_streams(stdout, stderr, exit_code)
    errors: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in combined.splitlines():
        line = raw_line.rstrip()
        match = _TSC_RE.match(line)
        if match:
            if current is not None:
                errors.append(current)
            current = {
                "path": match.group("path"),
                "line": match.group("line"),
                "code": match.group("code"),
                "message": match.group("message"),
                "context": "",
            }
            continue
        if current is not None and line.startswith((" ", "\t")) and line.strip():
            current["context"] = line.strip()
    if current is not None:
        errors.append(current)
    if not errors:
        text = "TypeScript: no errors found" if exit_code == 0 else combined.strip()
        return make_filter_result(
            text,
            filter_name="tsc",
            max_output_lines=max_output_lines,
        )
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    code_counter = Counter()
    for error in errors:
        by_file[error["path"]].append(error)
        code_counter[error["code"]] += 1
    lines = [f"TypeScript: {len(errors)} errors in {len(by_file)} files"]
    if len(code_counter) > 1:
        lines.append(
            "Top codes: "
            + ", ".join(
                f"{code} ({count}x)" for code, count in code_counter.most_common(5)
            )
        )
    for path, entries in sorted(
        by_file.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        lines.append(f"{_compact_path(path)} ({len(entries)})")
        for entry in entries:
            lines.append(
                f"  L{entry['line']}: {entry['code']} {_truncate(entry['message'])}"
            )
            if entry["context"]:
                lines.append(f"    {_truncate(entry['context'])}")
    return make_filter_result(
        "\n".join(lines),
        filter_name="tsc",
        max_output_lines=max_output_lines,
    )


def filter_next_output(
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
        "next build",
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    routes: list[tuple[str, float, float]] = []
    warnings = 0
    errors = 0
    static_routes = 0
    dynamic_routes = 0
    build_time = ""

    for raw_line in combined.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if "warning" in stripped.lower():
            warnings += 1
        if "error" in stripped.lower() and "0 errors" not in stripped.lower():
            errors += 1
        if stripped.startswith(("○ ", "┌ ○", "├ ○", "└ ○")):
            static_routes += 1
        elif stripped.startswith(("● ", "◐ ", "λ ", "ƒ ", "├ ●", "└ ●", "├ λ", "└ λ")):
            dynamic_routes += 1
        route_match = _NEXT_ROUTE_RE.match(stripped)
        if route_match:
            size = float(route_match.group("first"))
            if route_match.group("first_unit") == "B":
                size = size / 1000
            route_size = float(route_match.group("size"))
            if route_match.group("size_unit") == "B":
                route_size = route_size / 1000
            routes.append((route_match.group("route"), route_size, size))
        if "Compiled" in stripped or "Built in" in stripped:
            time_match = _NEXT_TIME_RE.search(stripped)
            if time_match:
                build_time = time_match.group("time").replace(" ", "")

    if exit_code != 0 and not routes and not build_time:
        return make_filter_result(
            generic.output,
            filter_name="next.build",
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    if not routes and not build_time and not combined.strip():
        return make_filter_result(
            "",
            filter_name="next.build",
            max_output_lines=max_output_lines,
        )

    lines = ["Next.js build"]
    total_routes = len({route for route, _, _ in routes}) or (
        static_routes + dynamic_routes
    )
    if total_routes:
        lines.append(
            f"{total_routes} routes ({static_routes} static, {dynamic_routes} dynamic)"
        )
    if routes:
        lines.append("Top bundles:")
        for route, route_size, first_load in sorted(routes, key=lambda item: -item[2])[
            :10
        ]:
            lines.append(
                f"  {_truncate(route, 30)} {first_load:.1f} kB first load ({route_size:.1f} kB route)"
            )
    status = f"Errors: {errors} | Warnings: {warnings}"
    if build_time:
        status = f"Time: {build_time} | {status}"
    lines.append(status)
    return make_filter_result(
        "\n".join(lines),
        filter_name="next.build",
        max_output_lines=max_output_lines,
        error=generic.error,
    )


def filter_cargo_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    combined = _combine_streams(stdout, stderr, exit_code)
    text, filter_name = _format_cargo_summary(command, combined, exit_code)
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
    )
