from __future__ import annotations

import re
from collections import defaultdict

from ..models import FilterResult
from .base import collapse_repeated_lines, make_filter_result, strip_ansi
from .generic import _combine_streams
from .generic import filter_generic_output

_NOISE_DIRS = frozenset({
    "node_modules", "target", "dist", "build", ".next",
    ".git", "__pycache__", ".venv", "venv", "env",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", ".vs",
    ".DS_Store", "Thumbs.db", ".cache", ".turbo", ".vercel",
    ".tox", ".nyc_output", ".eggs", "coverage", ".ruff_cache",
})

_LS_LINE_RE = re.compile(
    r"^([dlcbps-])"           # file type
    r"[rwxXsStT-]{9}[.+@]?"  # permissions
    r"\s+\d+"                 # link count
    r"\s+\S+"                 # owner
    r"\s+\S+"                 # group
    r"\s+(\d+)"              # size in bytes
    r"\s+\S+\s+\d+\s+[\d:]+\s+"  # date
    r"(.+)$"                  # filename (rest of line)
)


def _human_size(bytes_: int) -> str:
    if bytes_ >= 1_048_576:
        return f"{bytes_ / 1_048_576:.1f}M"
    if bytes_ >= 1024:
        return f"{bytes_ / 1024:.1f}K"
    return f"{bytes_}B"


def _compact_ls(text: str, *, show_all: bool = False) -> str | None:
    dirs: list[str] = []
    files: list[tuple[str, str]] = []  # (name, human_size)
    symlinks: list[str] = []
    ext_counts: dict[str, int] = defaultdict(int)

    for line in text.splitlines():
        if not line.strip() or line.startswith("total "):
            continue
        match = _LS_LINE_RE.match(line)
        if not match:
            continue
        file_type, size_str, name = match.group(1), match.group(2), match.group(3)
        name = name.strip()
        if name in {".", ".."}:
            continue
        if file_type == "d":
            if not show_all and name in _NOISE_DIRS:
                continue
            dirs.append(name)
        elif file_type == "l":
            symlinks.append(name)
        else:
            if not show_all and name in _NOISE_DIRS:
                continue
            files.append((name, _human_size(int(size_str))))
            dot_pos = name.rfind(".")
            ext = name[dot_pos:] if dot_pos > 0 else "no ext"
            ext_counts[ext] += 1

    if not dirs and not files and not symlinks:
        return None

    result: list[str] = []
    for d in sorted(dirs):
        result.append(f"{d}/")
    for name, size in sorted(files):
        result.append(f"{name}  {size}")
    for link in sorted(symlinks):
        result.append(link)

    # summary line
    top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:5]
    ext_summary = ", ".join(f"{ext} {count}" for ext, count in top_exts)
    summary_parts = []
    if files:
        summary_parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''}")
    if dirs:
        summary_parts.append(f"{len(dirs)} dir{'s' if len(dirs) != 1 else ''}")
    if symlinks:
        summary_parts.append(
            f"{len(symlinks)} symlink{'s' if len(symlinks) != 1 else ''}"
        )
    summary = ", ".join(summary_parts)
    if ext_summary:
        summary += f" ({ext_summary})"
    result.append("")
    result.append(summary)

    return "\n".join(result)


def _ls_show_all(command: str) -> bool:
    """Check if user explicitly asked to see all entries including noise dirs."""
    parts = command.split()
    for part in parts[1:]:
        if part == "--":
            break
        if part == "--all":
            return True
        if part == "-a" or part == "-A":
            return True
    return False


def filter_system_output(
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
    filter_name = "system"
    if command.strip().startswith("ls"):
        show_all = _ls_show_all(command.strip())
        compact = _compact_ls(combined, show_all=show_all)
        text = compact if compact is not None else generic.output
        filter_name = "system.ls"
    elif command.strip().startswith("cat "):
        text = strip_ansi(combined.replace("\r", "\n")).rstrip()
        filter_name = "system.read.cat"
    elif command.strip().startswith("head "):
        text = strip_ansi(combined.replace("\r", "\n")).rstrip()
        filter_name = "system.read.head"
    elif command.strip().startswith("tail "):
        text = collapse_repeated_lines(
            strip_ansi(combined.replace("\r", "\n")).rstrip(),
            max_run=1,
        )
        filter_name = "system.read.tail"
    elif command.strip().startswith(("grep ", "rg ")):
        filter_name = "system.grep"
    elif command.strip().startswith("find"):
        filter_name = "system.find"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
