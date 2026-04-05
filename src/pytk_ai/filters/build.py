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


def _format_cargo_summary(command: str, text: str, exit_code: int) -> tuple[str, str]:
    lowered = command.lower()
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
    subcommand = "clippy" if "cargo clippy" in lowered else "build"
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
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    severity_counter = Counter()
    for raw_line in text.splitlines():
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
