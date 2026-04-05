from __future__ import annotations

import json
import re

from ..models import FilterResult
from ..plan.normalize import normalize_absolute_first_token, strip_env_prefix
from .base import make_filter_result, strip_ansi
from .generic import _combine_streams, filter_generic_output

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_BADGE_LINE_RE = re.compile(r"(?m)^\s*\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)\s*$")
_IMAGE_ONLY_LINE_RE = re.compile(r"(?m)^\s*!\[[^\]]*\]\([^)]*\)\s*$")
_HORIZONTAL_RULE_RE = re.compile(r"(?m)^\s*(?:---+|\*\*\*+|___+)\s*$")
_GH_PREAMBLE_RE = re.compile(r"^showing\s+\d+\s+of\s+\d+", re.IGNORECASE)
_GH_ROW_SPLIT_RE = re.compile(r"\t+|\s{2,}")
_WGET_SAVING_RE = re.compile(r"(?:Saving to|Sauvegarde en)\s*[: ]\s*[\"'«](.*?)[\"'»]")
_WGET_SAVED_RE = re.compile(r"saved\s+\[(\d+)/(?:\d+)\]", re.IGNORECASE)


def _normalized_command(command: str) -> str:
    _, stripped = strip_env_prefix(command.strip())
    return normalize_absolute_first_token(stripped)


def _command_tokens(command: str) -> list[str]:
    normalized = _normalized_command(command)
    parts = normalized.split()
    if not parts:
        return []
    if parts[0] == "pytk-ai":
        return parts[1:]
    return parts


def _gh_mode(command: str) -> str | None:
    parts = _command_tokens(command)
    if len(parts) < 3 or parts[0] != "gh":
        return None
    if parts[1] == "pr" and parts[2] == "list":
        return "pr.list"
    if parts[1] == "pr" and parts[2] == "view":
        return "pr.view"
    if parts[1] == "issue" and parts[2] == "list":
        return "issue.list"
    if parts[1] == "run" and parts[2] == "list":
        return "run.list"
    return None


def _filter_markdown_segment(text: str) -> str:
    cleaned = _HTML_COMMENT_RE.sub("", text)
    cleaned = _BADGE_LINE_RE.sub("", cleaned)
    cleaned = _IMAGE_ONLY_LINE_RE.sub("", cleaned)
    cleaned = _HORIZONTAL_RULE_RE.sub("", cleaned)
    return _MULTI_BLANK_RE.sub("\n\n", cleaned)


def _filter_markdown_body(body: str) -> str:
    if not body:
        return ""
    result: list[str] = []
    remaining = body
    while remaining:
        fence_match = None
        for fence in ("```", "~~~"):
            idx = remaining.find(fence)
            if idx != -1 and (fence_match is None or idx < fence_match[0]):
                fence_match = (idx, fence)
        if fence_match is None:
            result.append(_filter_markdown_segment(remaining))
            break
        start, fence = fence_match
        before = remaining[:start]
        if before:
            result.append(_filter_markdown_segment(before))
        end = remaining.find(fence, start + len(fence))
        if end == -1:
            result.append(remaining[start:])
            break
        end += len(fence)
        newline = remaining.find("\n", end)
        if newline == -1:
            result.append(remaining[start:])
            break
        result.append(remaining[start : newline + 1])
        remaining = remaining[newline + 1 :]
    return "".join(result).strip()


def _is_probable_header(line: str) -> bool:
    columns = [part.strip() for part in _GH_ROW_SPLIT_RE.split(line) if part.strip()]
    if len(columns) < 2:
        return False
    if columns[0].startswith("#"):
        return False
    alpha_columns = [
        column for column in columns if any(char.isalpha() for char in column)
    ]
    if not alpha_columns:
        return False
    return all(column == column.upper() for column in alpha_columns)


def _normalize_gh_row(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or _GH_PREAMBLE_RE.match(stripped) or _is_probable_header(stripped):
        return None
    parts = [part.strip() for part in _GH_ROW_SPLIT_RE.split(stripped) if part.strip()]
    if not parts:
        return None
    if parts[0].isdigit():
        parts[0] = f"#{parts[0]}"
    elif parts[0].startswith("#") and " " in parts[0]:
        number, title = parts[0].split(" ", 1)
        parts = [number, title.strip(), *parts[1:]]
    if len(parts) >= 2:
        return " | ".join(parts)
    return parts[0]


def _summarize_gh_list(command: str, stdout: str, noun: str) -> str | None:
    rows = []
    for raw in strip_ansi(stdout).replace("\r", "\n").splitlines():
        row = _normalize_gh_row(raw)
        if row is not None:
            rows.append(row)
    lowered = stdout.lower()
    if not rows and f"no {noun}" in lowered:
        return f"{command}: 0 {noun}"
    if not rows:
        return None
    lines = [f"{command}: {len(rows)} {noun}"]
    lines.extend(rows[:10])
    if len(rows) > 10:
        lines.append(f"... +{len(rows) - 10} more")
    return "\n".join(lines)


def _summarize_pr_view(stdout: str) -> str | None:
    cleaned = _filter_markdown_body(strip_ansi(stdout).replace("\r", "\n")).strip()
    if not cleaned:
        return None
    if (cleaned.startswith("{") and cleaned.endswith("}")) or (
        cleaned.startswith("[") and cleaned.endswith("]")
    ):
        try:
            json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        else:
            return None
    lines = [line.rstrip() for line in cleaned.splitlines()]
    nonempty = [line.strip() for line in lines if line.strip()]
    if not nonempty:
        return None

    summary_lines: list[str] = []
    body_lines: list[str] = []
    in_body = False
    for line in lines:
        stripped = line.strip()
        if stripped == "--":
            in_body = True
            continue
        if not stripped:
            if in_body and body_lines and body_lines[-1] != "":
                body_lines.append("")
            continue
        if in_body:
            body_lines.append(line.rstrip())
            continue
        summary_lines.append(stripped)

    if not summary_lines:
        return None
    title = summary_lines[0]
    output = [f"gh pr view: {title}"]
    output.extend(summary_lines[1:8])
    if body_lines:
        trimmed_body = body_lines[:12]
        while trimmed_body and not trimmed_body[-1].strip():
            trimmed_body.pop()
        if trimmed_body:
            output.append("")
            output.extend(trimmed_body)
            if len(body_lines) > len(trimmed_body):
                output.append(
                    f"... +{len(body_lines) - len(trimmed_body)} more body lines"
                )
    return "\n".join(output)


def _json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "value"


def _render_json_schema(value: object, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]
        lines = [f"{prefix}{{"]
        items = list(value.items())
        for key, item in items[:12]:
            rendered = _render_json_schema(item, indent + 1)
            if len(rendered) == 1:
                lines.append(f"{'  ' * (indent + 1)}{key}: {rendered[0].strip()}")
            else:
                lines.append(f"{'  ' * (indent + 1)}{key}: {rendered[0].strip()}")
                lines.extend(rendered[1:])
        if len(items) > 12:
            lines.append(f"{'  ' * (indent + 1)}... +{len(items) - 12} more keys")
        lines.append(f"{prefix}}}")
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        sample = value[0]
        rendered = _render_json_schema(sample, indent + 1)
        lines = [f"{prefix}[len={len(value)}]"]
        if len(rendered) == 1:
            lines.append(f"{'  ' * (indent + 1)}{rendered[0].strip()}")
        else:
            lines.extend(rendered)
        return lines
    return [f"{prefix}{_json_type_name(value)}"]


def _summarize_curl(stdout: str) -> str:
    cleaned = strip_ansi(stdout).replace("\r", "\n").strip()
    if not cleaned:
        return ""
    if (cleaned.startswith("{") and cleaned.endswith("}")) or (
        cleaned.startswith("[") and cleaned.endswith("]")
    ):
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        else:
            schema = "\n".join(_render_json_schema(payload))
            if len(schema) <= len(cleaned):
                return schema
            return cleaned
    lines = cleaned.splitlines()
    if len(lines) > 30:
        kept = lines[:30]
        kept.append(f"... ({len(lines) - 30} more lines, {len(cleaned)} bytes total)")
        return "\n".join(kept)
    return "\n".join(line[:200] for line in lines)


def _curl_uses_download_mode(command: str) -> bool:
    parts = _command_tokens(command)
    if not parts or parts[0] != "curl":
        return False
    for index, part in enumerate(parts[1:], start=1):
        if part in {"-O", "--remote-name", "-o", "--output"}:
            return True
        if part.startswith("--output="):
            return True
        if part.startswith("-o") and part != "-o":
            return True
        if part.startswith("-O") and part != "-O":
            return True
        if part in {"-OJ", "--remote-header-name"}:
            return True
        if part.startswith("-"):
            continue
        _ = index
    return False


def _extract_url(command: str, tool: str) -> str:
    parts = _command_tokens(command)
    if not parts or parts[0] != tool:
        return ""
    for part in reversed(parts[1:]):
        if "://" in part:
            return part
    return ""


def _compact_url(url: str) -> str:
    if not url:
        return "wget"
    compact = url.removeprefix("https://").removeprefix("http://")
    if len(compact) <= 50:
        return compact
    return f"{compact[:25]}...{compact[-20:]}"


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "?"
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _extract_wget_filename(command: str, stderr: str, url: str) -> str:
    parts = _command_tokens(command)
    for index, part in enumerate(parts):
        if part in {"-O", "--output-document"} and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith("--output-document="):
            return part.split("=", 1)[1]
        if part.startswith("-O") and part != "-O":
            return part[2:]
    for raw in stderr.splitlines():
        match = _WGET_SAVING_RE.search(raw)
        if match:
            return match.group(1).strip()
    if url:
        candidate = url.rsplit("/", 1)[-1].split("?", 1)[0]
        if candidate and "." in candidate:
            return candidate
    return "index.html"


def _extract_wget_size(stderr: str) -> int | None:
    for raw in stderr.splitlines():
        match = _WGET_SAVED_RE.search(raw)
        if match:
            return int(match.group(1))
    return None


def _parse_wget_error(stderr: str, stdout: str) -> str | None:
    combined = f"{stderr}\n{stdout}"
    patterns = (
        ("404", "404 Not Found"),
        ("403", "403 Forbidden"),
        ("401", "401 Unauthorized"),
        ("500", "500 Server Error"),
        ("Connection refused", "Connection refused"),
        ("unable to resolve", "DNS lookup failed"),
        ("Name or service not known", "DNS lookup failed"),
        ("timed out", "Connection timed out"),
        ("SSL", "SSL/TLS error"),
        ("certificate", "SSL/TLS error"),
    )
    for needle, label in patterns:
        if needle in combined:
            return label
    for raw in stderr.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("--"):
            return stripped[:120]
    return None


def filter_github_api_output(
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
    parts = _command_tokens(command)
    if not parts:
        return generic

    if parts[0] == "gh":
        mode = _gh_mode(command)
        filter_name = f"gh.{mode}" if mode else "gh"
        if exit_code != 0 or mode is None:
            return make_filter_result(
                _combine_streams(stdout, stderr, exit_code),
                filter_name=filter_name,
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        if mode == "pr.list":
            text = _summarize_gh_list("gh pr list", stdout, "pull requests")
        elif mode == "issue.list":
            text = _summarize_gh_list("gh issue list", stdout, "issues")
        elif mode == "run.list":
            text = _summarize_gh_list("gh run list", stdout, "runs")
        else:
            text = _summarize_pr_view(stdout)
        return make_filter_result(
            text or _combine_streams(stdout, stderr, exit_code),
            filter_name=filter_name,
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    if parts[0] == "curl":
        if exit_code != 0:
            return make_filter_result(
                _combine_streams(stdout, stderr, exit_code),
                filter_name="curl",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        if _curl_uses_download_mode(command) or not stdout.strip():
            return make_filter_result(
                _combine_streams(stdout, stderr, exit_code),
                filter_name="curl",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        return make_filter_result(
            _summarize_curl(stdout),
            filter_name="curl",
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    if parts[0] == "wget":
        url = _extract_url(command, "wget")
        if exit_code != 0:
            error = _parse_wget_error(stderr, stdout)
            text = (
                f"{_compact_url(url)} FAILED: {error}"
                if error is not None
                else _combine_streams(stdout, stderr, exit_code)
            )
            return make_filter_result(
                text,
                filter_name="wget",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        if stdout.strip():
            return make_filter_result(
                strip_ansi(stdout).replace("\r", "\n").rstrip(),
                filter_name="wget",
                max_output_lines=max_output_lines,
                error=generic.error,
            )
        filename = _extract_wget_filename(command, stderr, url)
        size = _format_size(_extract_wget_size(stderr))
        return make_filter_result(
            f"{_compact_url(url)} ok | {filename} | {size}",
            filter_name="wget",
            max_output_lines=max_output_lines,
            error=generic.error,
        )

    return generic
