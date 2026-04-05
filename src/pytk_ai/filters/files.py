from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePath

from ..models import FilterResult
from ..plan.normalize import normalize_absolute_first_token, strip_env_prefix
from .base import (
    collapse_repeated_lines,
    make_filter_result,
    strip_ansi,
    truncate_lines,
)
from .generic import _combine_streams, filter_generic_output

_GREP_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<text>.*)$")
_WC_LINE_RE = re.compile(r"^\s*(?P<counts>(?:\d+\s+){0,3}\d+)(?:\s+(?P<label>.+))?$")
_TREE_SUMMARY_RE = re.compile(
    r"(?P<dirs>\d+)\s+directories?,\s+(?P<files>\d+)\s+files?$"
)


def _command_name(command: str) -> str:
    _, stripped = strip_env_prefix(command.strip())
    normalized = normalize_absolute_first_token(stripped)
    if normalized.startswith("pytk-ai "):
        parts = normalized.split(maxsplit=2)
        return parts[1] if len(parts) > 1 else "pytk-ai"
    return normalized.split(maxsplit=1)[0] if normalized else ""


def _command_filter_name(command: str, subname: str | None = None) -> str:
    name = _command_name(command) or "files"
    return f"{name}.{subname}" if subname else name


def _read_filter_name(command_name: str) -> str:
    if command_name == "cat":
        return "system.read.cat"
    if command_name == "head":
        return "system.read.head"
    if command_name == "tail":
        return "system.read.tail"
    return "read"


def _raw_read_output(
    command_name: str, stdout: str, stderr: str, exit_code: int
) -> str:
    combined = strip_ansi(
        _combine_streams(stdout, stderr, exit_code).replace("\r", "\n")
    )
    if command_name == "tail":
        return collapse_repeated_lines(combined.rstrip(), max_run=1)
    return combined.rstrip()


def _make_read_result(
    command_name: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int,
    error: str | None,
) -> FilterResult:
    text = _raw_read_output(command_name, stdout, stderr, exit_code)
    truncated_text, truncated = truncate_lines(text, max_output_lines)
    return FilterResult(
        output=truncated_text,
        filter_name=_read_filter_name(command_name),
        error=error,
        truncated=truncated,
    )


def _summarize_grep(text: str) -> str | None:
    by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
    total_matches = 0
    for raw in text.splitlines():
        match = _GREP_LINE_RE.match(raw)
        if not match:
            continue
        total_matches += 1
        by_file[match.group("path")].append(
            (int(match.group("line")), match.group("text").strip())
        )
    if not by_file:
        return None
    lines = [f"Search: {total_matches} matches in {len(by_file)} files"]
    shown = 0
    for path, matches in sorted(by_file.items()):
        lines.append(f"{path} ({len(matches)})")
        for line_no, content in matches[:3]:
            lines.append(f"  {line_no}: {content}")
            shown += 1
        if len(matches) > 3:
            lines.append(f"  ... +{len(matches) - 3} more")
    if total_matches > shown:
        lines.append(f"... +{total_matches - shown} more matches")
    return "\n".join(lines)


def _summarize_find(text: str) -> str | None:
    paths = [line.strip() for line in text.splitlines() if line.strip()]
    if not paths:
        return "0 matches"
    by_dir: dict[str, list[str]] = defaultdict(list)
    for raw_path in paths:
        path = PurePath(raw_path)
        parent = str(path.parent) if str(path.parent) not in {"", "."} else "."
        by_dir[parent].append(path.name or raw_path)
    lines = [f"Find: {len(paths)} paths in {len(by_dir)} directories"]
    shown = 0
    for directory, names in sorted(by_dir.items()):
        sorted_names = sorted(names)
        lines.append(f"{directory} ({len(sorted_names)})")
        for name in sorted_names[:4]:
            lines.append(f"  {name}")
            shown += 1
        if len(sorted_names) > 4:
            lines.append(f"  ... +{len(sorted_names) - 4} more")
    if len(paths) > shown:
        lines.append(f"... +{len(paths) - shown} more paths")
    return "\n".join(lines)


def _summarize_tree(text: str) -> str | None:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    summary_match = None
    for line in reversed(lines):
        summary_match = _TREE_SUMMARY_RE.search(line)
        if summary_match:
            break
    if summary_match is None:
        return None
    entries = [
        line
        for line in lines
        if line != "."
        and _TREE_SUMMARY_RE.search(line) is None
        and not line.startswith("[")
    ]
    output = [
        "tree: "
        f"{summary_match.group('dirs')} directories, {summary_match.group('files')} files"
    ]
    output.extend(entries[:10])
    if len(entries) > 10:
        output.append(f"... +{len(entries) - 10} more entries")
    return "\n".join(output)


def _wc_metric_names(command: str) -> tuple[str, ...] | None:
    _, stripped = strip_env_prefix(command.strip())
    normalized = normalize_absolute_first_token(stripped)
    parts = normalized.split()
    if not parts:
        return None

    if parts[0] == "pytk-ai":
        if len(parts) < 2 or parts[1] != "wc":
            return None
        args = parts[2:]
    elif parts[0] == "wc":
        args = parts[1:]
    else:
        return None

    metrics: list[str] = []
    explicit = False
    long_map = {
        "--lines": "lines",
        "--words": "words",
        "--chars": "chars",
        "--bytes": "bytes",
        "--max-line-length": "max-line-length",
    }
    short_map = {
        "l": "lines",
        "w": "words",
        "m": "chars",
        "c": "bytes",
        "L": "max-line-length",
    }

    for arg in args:
        if arg == "--":
            break
        if not arg.startswith("-") or arg == "-":
            continue
        if arg in long_map:
            explicit = True
            metric = long_map[arg]
            if metric not in metrics:
                metrics.append(metric)
            continue
        if arg.startswith("--"):
            return None
        explicit = True
        for flag in arg[1:]:
            metric = short_map.get(flag)
            if metric is None:
                return None
            if metric not in metrics:
                metrics.append(metric)

    if not explicit:
        return ("lines", "words", "bytes")
    return tuple(metrics)


def _format_wc_counts(
    numbers: list[int], metric_names: tuple[str, ...] | None
) -> str | None:
    if metric_names is None or len(metric_names) != len(numbers):
        return None
    names = metric_names
    return ", ".join(f"{value} {name}" for value, name in zip(numbers, names))


def _summarize_wc(command: str, text: str) -> str | None:
    metric_names = _wc_metric_names(command)
    entries: list[tuple[str, list[int]]] = []
    for raw in text.splitlines():
        match = _WC_LINE_RE.match(raw)
        if not match:
            continue
        counts = [int(part) for part in match.group("counts").split()]
        label = (match.group("label") or "<stdin>").strip()
        entries.append((label, counts))
    if not entries:
        return None
    if len(entries) == 1:
        label, counts = entries[0]
        summary = _format_wc_counts(counts, metric_names)
        if summary is None:
            return None
        return f"wc {label}: {summary}"
    total_entry = next((entry for entry in entries if entry[0] == "total"), None)
    lines = []
    if total_entry is not None:
        total_summary = _format_wc_counts(total_entry[1], metric_names)
        if total_summary is None:
            return None
        lines.append(f"wc total: {total_summary} across {len(entries) - 1} files")
    else:
        lines.append(f"wc: {len(entries)} entries")
    for label, counts in entries[:6]:
        if label == "total":
            continue
        summary = _format_wc_counts(counts, metric_names)
        if summary is None:
            return None
        lines.append(f"{label}: {summary}")
    extra = len([label for label, _ in entries if label != "total"]) - min(
        len([label for label, _ in entries if label != "total"]), 6
    )
    if extra > 0:
        lines.append(f"... +{extra} more files")
    return "\n".join(lines)


def _summarize_diff(text: str) -> str | None:
    lines = text.splitlines()
    current_file: str | None = None
    pending_old: str | None = None
    added = 0
    removed = 0
    changes: list[str] = []
    result: list[str] = []

    def clean_label(label: str) -> str:
        return label.removeprefix("a/").removeprefix("b/")

    def flush() -> None:
        nonlocal current_file, added, removed, changes
        if current_file is None:
            return
        result.append(f"{current_file} (+{added}/-{removed})")
        result.extend(changes[:4])
        if len(changes) > 4:
            result.append(f"  ... +{len(changes) - 4} more changes")
        current_file = None
        added = 0
        removed = 0
        changes = []

    for line in lines:
        if line.startswith("diff --git "):
            flush()
            parts = line.split()
            if len(parts) >= 4:
                current_file = clean_label(parts[3])
            pending_old = None
            continue
        if line.startswith("--- "):
            pending_old = clean_label(line[4:].strip())
            if current_file is None and pending_old != "/dev/null":
                current_file = pending_old
            continue
        if line.startswith("+++ "):
            new_path = clean_label(line[4:].strip())
            if new_path != "/dev/null":
                current_file = new_path
            elif current_file is None:
                current_file = pending_old
            continue
        if line.startswith("@@") or line.startswith("index "):
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
            changes.append(f"  + {line[1:].strip()}")
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
            changes.append(f"  - {line[1:].strip()}")
    flush()
    return "\n".join(result) if result else None


def filter_file_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    generic = filter_generic_output(
        command,
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    command_name = _command_name(command)
    filter_name = _command_filter_name(command)

    if command_name in {"cat", "head", "tail", "read"}:
        return _make_read_result(
            command_name,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    combined = _combine_streams(stdout, stderr, exit_code)
    if command_name in {"rg", "grep"}:
        filter_name = "search.grep"
    elif command_name == "find":
        filter_name = "search.find"
    elif command_name == "tree":
        filter_name = "files.tree"
    elif command_name == "wc":
        filter_name = "files.wc"
    elif command_name == "diff":
        filter_name = "files.diff"

    if command_name in {"rg", "grep"} and exit_code == 1 and not combined.strip():
        return make_filter_result(
            "0 matches",
            filter_name=filter_name,
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    if command_name == "diff" and exit_code in {0, 1}:
        text = _summarize_diff(combined) or generic.output
        return make_filter_result(
            text,
            filter_name=filter_name,
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    if exit_code != 0:
        return make_filter_result(
            combined,
            filter_name=filter_name,
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    text = generic.output
    if command_name in {"rg", "grep"}:
        text = _summarize_grep(combined) or (
            "0 matches" if not combined.strip() else generic.output
        )
    elif command_name == "find":
        text = _summarize_find(combined) or generic.output
    elif command_name == "tree":
        text = _summarize_tree(combined) or generic.output
    elif command_name == "wc":
        text = _summarize_wc(command, combined) or generic.output
    elif command_name == "diff":
        text = _summarize_diff(combined) or generic.output

    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
