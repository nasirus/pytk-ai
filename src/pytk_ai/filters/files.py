from __future__ import annotations

from dataclasses import dataclass
import re
from collections import defaultdict
from pathlib import PurePath
import shlex

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
_MULTIPLE_BLANK_LINES_RE = re.compile(r"\n{3,}")
_IMPORT_PATTERN = re.compile(r"^(use |import |from |require\(|#include)")
_SIGNATURE_PATTERN = re.compile(
    r"^(?:pub\s+)?(?:async\s+)?(?:fn|def|function|func|class|struct|enum|trait|interface|type)\s+\w+"
)


@dataclass(frozen=True)
class _CommentPatterns:
    line: str | None = None
    block_start: str | None = None
    block_end: str | None = None
    doc_line: str | None = None
    doc_block_start: str | None = None


_LANGUAGE_PATTERNS = {
    "rust": _CommentPatterns(
        line="//",
        block_start="/*",
        block_end="*/",
        doc_line="///",
        doc_block_start="/**",
    ),
    "python": _CommentPatterns(
        line="#",
        block_start='"""',
        block_end='"""',
        doc_block_start='"""',
    ),
    "javascript": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "typescript": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "go": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "c": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "cpp": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "java": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
    "ruby": _CommentPatterns(line="#", block_start="=begin", block_end="=end"),
    "shell": _CommentPatterns(line="#"),
    "data": _CommentPatterns(),
    "unknown": _CommentPatterns(line="//", block_start="/*", block_end="*/"),
}
_DATA_EXTENSIONS = {
    "json",
    "jsonc",
    "json5",
    "yaml",
    "yml",
    "toml",
    "xml",
    "csv",
    "tsv",
    "graphql",
    "gql",
    "sql",
    "md",
    "markdown",
    "txt",
    "env",
    "lock",
}


def _detect_language(path: str | None) -> str:
    if not path:
        return "unknown"
    suffix = PurePath(path).suffix.lower().lstrip(".")
    if suffix == "rs":
        return "rust"
    if suffix in {"py", "pyw"}:
        return "python"
    if suffix in {"js", "mjs", "cjs"}:
        return "javascript"
    if suffix in {"ts", "tsx"}:
        return "typescript"
    if suffix == "go":
        return "go"
    if suffix in {"c", "h"}:
        return "c"
    if suffix in {"cpp", "cc", "cxx", "hpp", "hh"}:
        return "cpp"
    if suffix == "java":
        return "java"
    if suffix == "rb":
        return "ruby"
    if suffix in {"sh", "bash", "zsh"}:
        return "shell"
    if suffix in _DATA_EXTENSIONS:
        return "data"
    return "unknown"


def _normalize_filtered_text(text: str) -> str:
    normalized = _MULTIPLE_BLANK_LINES_RE.sub("\n\n", text)
    return normalized.strip()


def _apply_minimal_filter(content: str, language: str) -> str:
    patterns = _LANGUAGE_PATTERNS[language]
    result: list[str] = []
    in_block_comment = False
    in_docstring = False

    for line in content.splitlines():
        trimmed = line.strip()

        if (
            patterns.block_start is not None
            and patterns.block_end is not None
            and not in_docstring
            and patterns.block_start in trimmed
            and not trimmed.startswith(patterns.doc_block_start or "###")
        ):
            in_block_comment = True

        if in_block_comment:
            if patterns.block_end is not None and patterns.block_end in trimmed:
                in_block_comment = False
            continue

        if language == "python" and trimmed.startswith('"""'):
            in_docstring = not in_docstring
            result.append(line)
            continue

        if in_docstring:
            result.append(line)
            continue

        if patterns.line is not None and trimmed.startswith(patterns.line):
            if patterns.doc_line is not None and trimmed.startswith(patterns.doc_line):
                result.append(line)
            continue

        if not trimmed:
            result.append("")
            continue

        result.append(line)

    return _normalize_filtered_text("\n".join(result))


def _apply_aggressive_filter(content: str, language: str) -> str:
    if language == "data":
        return _apply_minimal_filter(content, language)

    minimal = _apply_minimal_filter(content, language)
    result: list[str] = []
    brace_depth = 0
    in_impl_body = False

    for line in minimal.splitlines():
        trimmed = line.strip()

        if _IMPORT_PATTERN.match(trimmed):
            result.append(line)
            continue

        if _SIGNATURE_PATTERN.match(trimmed):
            result.append(line)
            in_impl_body = True
            brace_depth = 0
            continue

        open_braces = trimmed.count("{")
        close_braces = trimmed.count("}")

        if in_impl_body:
            brace_depth += open_braces
            brace_depth -= close_braces
            if brace_depth <= 1 and (trimmed in {"{", "}"} or trimmed.endswith("{")):
                result.append(line)
            if brace_depth <= 0:
                in_impl_body = False
                if trimmed and trimmed != "}":
                    result.append("    # ... implementation")
            continue

        if trimmed.startswith(
            ("const ", "static ", "let ", "pub const ", "pub static ")
        ):
            result.append(line)

    return _normalize_filtered_text("\n".join(result))


def _apply_read_level(content: str, level: str, language: str) -> str:
    if level == "minimal":
        return _apply_minimal_filter(content, language)
    if level == "aggressive":
        return _apply_aggressive_filter(content, language)
    return content


def smart_truncate_read(content: str, max_lines: int, language: str) -> str:
    lines = content.splitlines()
    if max_lines <= 0:
        return ""
    if len(lines) <= max_lines:
        return content

    result: list[str] = []
    kept_lines = 0
    skipped_section = False

    for line in lines:
        trimmed = line.strip()
        is_important = bool(
            _SIGNATURE_PATTERN.match(trimmed)
            or _IMPORT_PATTERN.match(trimmed)
            or trimmed.startswith(("pub ", "export "))
            or trimmed in {"{", "}"}
        )

        if is_important or kept_lines < max_lines // 2:
            if skipped_section:
                result.append(f"    # ... {len(lines) - kept_lines} lines omitted")
                skipped_section = False
            result.append(line)
            kept_lines += 1
        else:
            skipped_section = True

        if kept_lines >= max_lines - 1:
            break

    if skipped_section or kept_lines < len(lines):
        result.append(
            f"# ... {len(lines) - kept_lines} more lines (total: {len(lines)})"
        )

    return "\n".join(result)


def apply_read_window(
    content: str,
    *,
    max_lines: int | None,
    tail_lines: int | None,
    language: str,
) -> str:
    if tail_lines is not None:
        if tail_lines <= 0:
            return ""
        lines = content.splitlines()
        result = "\n".join(lines[-tail_lines:])
        if content.endswith("\n") and result:
            result += "\n"
        return result

    if max_lines is not None:
        return smart_truncate_read(content, max_lines, language)

    return content


def format_with_line_numbers(content: str) -> str:
    lines = content.splitlines()
    if not lines:
        return ""
    width = len(str(len(lines)))
    return "\n".join(
        f"{index:>{width}} | {line}" for index, line in enumerate(lines, start=1)
    )


def render_read_output(
    content: str,
    *,
    source_path: str | None,
    level: str = "none",
    max_lines: int | None = None,
    tail_lines: int | None = None,
    line_numbers: bool = False,
) -> str:
    language = _detect_language(source_path)
    filtered = _apply_read_level(content, level, language)
    if not filtered.strip() and content.strip():
        filtered = content
    filtered = apply_read_window(
        filtered,
        max_lines=max_lines,
        tail_lines=tail_lines,
        language=language,
    )
    if line_numbers:
        filtered = format_with_line_numbers(filtered)
    return filtered


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


def _extract_pytk_read_args(
    command: str,
) -> tuple[str | None, str, int | None, int | None, bool]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None, "none", None, None, False

    if len(tokens) < 2 or tokens[0] != "pytk-ai" or tokens[1] != "read":
        return None, "none", None, None, False

    source_path: str | None = None
    level = "none"
    max_lines: int | None = None
    tail_lines: int | None = None
    line_numbers = False
    index = 2
    while index < len(tokens):
        token = tokens[index]
        if token in {"--level", "-l"}:
            index += 1
            if index >= len(tokens):
                break
            level = tokens[index]
        elif token.startswith("--level="):
            level = token.split("=", 1)[1]
        elif token in {"--max-lines", "-m"}:
            index += 1
            if index >= len(tokens):
                break
            try:
                max_lines = int(tokens[index])
            except ValueError:
                max_lines = None
        elif token.startswith("--max-lines="):
            try:
                max_lines = int(token.split("=", 1)[1])
            except ValueError:
                max_lines = None
        elif token == "--tail-lines":
            index += 1
            if index >= len(tokens):
                break
            try:
                tail_lines = int(tokens[index])
            except ValueError:
                tail_lines = None
        elif token.startswith("--tail-lines="):
            try:
                tail_lines = int(token.split("=", 1)[1])
            except ValueError:
                tail_lines = None
        elif token in {"--line-numbers", "-n"}:
            line_numbers = True
        elif source_path is None:
            source_path = token
        index += 1

    if level not in {"none", "minimal", "aggressive"}:
        level = "none"
    return source_path, level, max_lines, tail_lines, line_numbers


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
    command: str,
    command_name: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int,
    error: str | None,
) -> FilterResult:
    text = _raw_read_output(command_name, stdout, stderr, exit_code)
    source_path = None
    level = "none"
    read_max_lines = None
    tail_lines = None
    line_numbers = False

    if command_name == "read":
        source_path, level, read_max_lines, tail_lines, line_numbers = (
            _extract_pytk_read_args(command)
        )
    rendered = render_read_output(
        text,
        source_path=source_path,
        level=level,
        max_lines=read_max_lines,
        tail_lines=tail_lines,
        line_numbers=line_numbers,
    )
    truncated_text, truncated = truncate_lines(rendered, max_output_lines)
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


def _summarize_find_rtk_style(text: str) -> str | None:
    paths = sorted(line.strip() for line in text.splitlines() if line.strip())
    if not paths:
        return "0 for '*'"

    by_dir: dict[str, list[str]] = defaultdict(list)
    by_ext: dict[str, int] = defaultdict(int)
    for raw_path in paths:
        path = PurePath(raw_path)
        parent = str(path.parent) if str(path.parent) not in {"", "."} else "."
        name = path.name or raw_path
        by_dir[parent].append(name)
        suffix = path.suffix[1:] if path.suffix else "none"
        by_ext[suffix] += 1

    lines = [f"{len(paths)}F {len(by_dir)}D:", ""]
    shown = 0
    for directory in sorted(by_dir):
        names = sorted(by_dir[directory])
        if shown >= 50:
            break
        remaining_budget = 50 - shown
        displayed = names[:remaining_budget]
        dir_display = directory if len(directory) <= 50 else f"...{directory[-47:]}"
        lines.append(f"{dir_display}/ {' '.join(displayed)}")
        shown += len(displayed)
        if len(displayed) < len(names):
            break

    if shown < len(paths):
        lines.append(f"+{len(paths) - shown} more")

    if len(by_ext) > 1:
        ext_summary = " ".join(
            f".{ext}({count})"
            for ext, count in sorted(
                by_ext.items(), key=lambda item: (-item[1], item[0])
            )[:5]
        )
        lines.extend(["", f"ext: {ext_summary}"])

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
        return label.split("\t", 1)[0].removeprefix("a/").removeprefix("b/")

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


def _looks_like_direct_diff_command(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    if tokens[0] in {"pytk-ai", "python", "python3"}:
        return False
    if tokens[0] != "diff":
        return False
    args = tokens[1:]
    return len(args) == 2 and all(not arg.startswith("-") for arg in args)


def _summarize_direct_diff(
    command: str, stdout: str, stderr: str, exit_code: int
) -> str | None:
    if not _looks_like_direct_diff_command(command):
        return None
    if stderr.strip():
        return None
    summary = _summarize_diff(stdout)
    if summary is None:
        if exit_code == 0:
            return "[ok] Files are identical"
        return None

    lines = summary.splitlines()
    if not lines:
        return None

    header = lines[0]
    match = re.match(r"^(?P<path>.+) \(\+(?P<added>\d+)/-(?P<removed>\d+)\)$", header)
    if match is None:
        return summary

    path = match.group("path")
    added = int(match.group("added"))
    removed = int(match.group("removed"))
    body = [path, f"   +{added} added, -{removed} removed, ~0 modified", ""]
    body.extend(lines[1:])
    return "\n".join(body).rstrip()


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
            command,
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
        text = (
            _summarize_direct_diff(command, stdout, stderr, exit_code)
            or _summarize_diff(combined)
            or generic.output
        )
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
        text = (
            _summarize_find_rtk_style(combined)
            or _summarize_find(combined)
            or generic.output
        )
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
