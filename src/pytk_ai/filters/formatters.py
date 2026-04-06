from __future__ import annotations

import os
import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_PRETTIER_WARN_PATH_RE = re.compile(r"^\[warn\]\s+(?P<path>.+)$")
_PRETTIER_ISSUES_RE = re.compile(
    r"Code style issues found in (?P<count>\d+) files?", re.IGNORECASE
)
_PRETTIER_WRITE_PREFIX_RE = re.compile(r"^(?P<status>\[[^\]]+\]|\w+)\s+(?P<path>.+)$")
_PRETTIER_WRITTEN_PATH_RE = re.compile(
    r"^(?P<path>.+?\.(?:[cm]?[jt]sx?|json|md|css|scss|html|yaml|yml|vue|astro))(?:\s+\d+(?:\.\d+)?(?:ms|s))?$",
    re.IGNORECASE,
)
_PRETTIER_PATH_RE = re.compile(
    r"^.+\.(?:[cm]?[jt]sx?|json|md|css|scss|html|yaml|yml|vue|astro)$",
    re.IGNORECASE,
)
_BIOME_CHECKED_RE = re.compile(r"^Checked\s+\d+\s+file", re.IGNORECASE)
_BIOME_FIXED_RE = re.compile(r"^Fixed\s+\d+\s+file", re.IGNORECASE)
_BIOME_FORMAT_COUNT_RE = re.compile(
    r"^(?P<count>\d+)\s+files?\s+(?P<kind>would be|were)\s+formatted", re.IGNORECASE
)
_BIOME_FORMAT_PATH_RE = re.compile(
    r"^(?:Formatted|Would format|Would fix|Fixed)\s+(?P<path>.+)$", re.IGNORECASE
)


def _compact_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    for marker in ("/src/", "/lib/", "/tests/"):
        if marker in normalized:
            prefix, suffix = normalized.split(marker, 1)
            del prefix
            return marker[1:] + suffix
    if normalized.startswith("/"):
        return os.path.basename(normalized) or normalized
    return normalized or os.path.basename(normalized)


def _looks_like_path(line: str) -> bool:
    return bool(_PRETTIER_PATH_RE.match(line))


def _is_prettier_write_command(command: str) -> bool:
    lowered = command.lower()
    return any(
        flag in lowered
        for flag in (" --write", " --check=false", " --list-different=false")
    )


def _filter_prettier(text: str, *, prefer_write: bool = False) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None

    check_files: list[str] = []
    written_files: list[str] = []
    count = 0
    mode = "write" if prefer_write else "check"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("checking formatting"):
            mode = "check"
            continue
        if lower.startswith(
            ("[warn] code style issues found in", "code style issues found in")
        ):
            count_match = _PRETTIER_ISSUES_RE.search(line)
            if count_match:
                count = int(count_match.group("count"))
            continue
        if "all matched files use prettier code style" in lower:
            return "Format (prettier): all files formatted"
        match = _PRETTIER_WARN_PATH_RE.match(line)
        if match:
            path = match.group("path")
            if _looks_like_path(path):
                check_files.append(path)
            continue

        write_match = _PRETTIER_WRITE_PREFIX_RE.match(line)
        if write_match:
            status = write_match.group("status").strip("[]").lower()
            path = write_match.group("path")
            if _looks_like_path(path) and status in {
                "write",
                "wrote",
                "formatted",
                "rewrite",
            }:
                mode = "write"
                written_files.append(path)
                continue

        written_match = _PRETTIER_WRITTEN_PATH_RE.match(line)
        if written_match:
            path = written_match.group("path")
            if mode == "write":
                written_files.append(path)
            else:
                check_files.append(path)

    if check_files or count:
        total = max(len(check_files), count)
        lines = [f"Format (prettier): {total} files need formatting"]
        for path in check_files[:10]:
            lines.append(f"  {_compact_path(path)}")
        if len(check_files) > 10:
            lines.append(f"... +{len(check_files) - 10} more files")
        return "\n".join(lines)
    if written_files:
        lines = [f"Format (prettier): {len(written_files)} files formatted"]
        for path in written_files[:10]:
            lines.append(f"  {_compact_path(path)}")
        if len(written_files) > 10:
            lines.append(f"... +{len(written_files) - 10} more files")
        return "\n".join(lines)
    return None


def _filter_black(text: str) -> str | None:
    files: list[str] = []
    reformatted = 0
    unchanged = 0
    all_done = False
    oh_no = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("would reformat:"):
            files.append(line.split(":", 1)[1].strip())
        if "would be reformatted" in lower or "would be left unchanged" in lower:
            for part in line.split(","):
                part_lower = part.lower()
                words = part.split()
                for index, word in enumerate(words):
                    if word not in {"file", "files"} or index == 0:
                        continue
                    try:
                        count = int(words[index - 1])
                    except ValueError:
                        continue
                    if "would be reformatted" in part_lower:
                        reformatted = count
                    if "would be left unchanged" in part_lower:
                        unchanged = count
        if "left unchanged" in lower and "would be" not in lower:
            words = line.split()
            for index, word in enumerate(words):
                if word in {"file", "files"} and index > 0:
                    try:
                        unchanged = int(words[index - 1])
                    except ValueError:
                        pass
                    break
        if "all done!" in lower:
            all_done = True
        if "oh no!" in lower:
            oh_no = True

    needs_formatting = bool(files or reformatted or oh_no)
    if not needs_formatting and (all_done or unchanged):
        summary = "Format (black): all files formatted"
        if unchanged:
            summary += f" ({unchanged} files checked)"
        return summary
    if needs_formatting:
        total = len(files) or reformatted
        lines = [f"Format (black): {total} files need formatting"]
        for path in files[:10]:
            lines.append(f"  {_compact_path(path)}")
        if len(files) > 10:
            lines.append(f"... +{len(files) - 10} more files")
        if unchanged:
            lines.append(f"{unchanged} files already formatted")
        lines.append("[hint] Run `black .` to format these files")
        return "\n".join(lines)
    return None


def _filter_biome(text: str, exit_code: int) -> str | None:
    lines: list[str] = []
    formatted_files: list[str] = []
    would_format = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _BIOME_CHECKED_RE.match(line) or _BIOME_FIXED_RE.match(line):
            continue
        if line.startswith("The following command") or line.startswith("Run it with"):
            continue
        count_match = _BIOME_FORMAT_COUNT_RE.match(line)
        if count_match:
            would_format = int(count_match.group("count"))
            continue
        path_match = _BIOME_FORMAT_PATH_RE.match(line)
        if path_match:
            formatted_files.append(path_match.group("path"))
            continue
        lines.append(line)

    if formatted_files:
        output = [f"Format (biome): {len(formatted_files)} files formatted"]
        for path in formatted_files[:10]:
            output.append(f"  {_compact_path(path)}")
        if len(formatted_files) > 10:
            output.append(f"... +{len(formatted_files) - 10} more files")
        return "\n".join(output)
    if would_format:
        return f"Format (biome): {would_format} files need formatting"
    stripped = "\n".join(lines).strip()
    if not stripped and exit_code == 0:
        return "biome: ok"
    lowered = stripped.lower()
    if exit_code == 0 and (
        "no fixes applied" in lowered
        or "checked " in lowered
        or "formatted " in lowered
    ):
        return "biome: ok"
    return stripped or None


def filter_format_output(
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
    if "prettier" in lowered:
        text = (
            _filter_prettier(combined, prefer_write=_is_prettier_write_command(command))
            or generic.output
        )
        filter_name = "format.prettier"
    elif "black" in lowered:
        text = _filter_black(combined) or generic.output
        filter_name = "format.black"
    elif "biome" in lowered:
        text = _filter_biome(combined, exit_code) or generic.output
        filter_name = "format.biome"
    else:
        formatter = "ruff" if "ruff" in lowered else "auto"
        if formatter == "auto" and _is_prettier_write_command(command):
            text = _filter_prettier(combined, prefer_write=True) or generic.output
            filter_name = "format.prettier"
        else:
            text = generic.output
            filter_name = "format"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
