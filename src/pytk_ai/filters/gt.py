from __future__ import annotations

import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BRANCH_NAME_RE = re.compile(
    r"(?:Created|Pushed|pushed|Deleted|deleted)\s+branch\s+[`\"']?([a-zA-Z0-9/_.\-+@]+)"
)
_PR_LINE_RE = re.compile(
    r"(Created|Updated)\s+pull\s+request\s+#(\d+)\s+for\s+([^\s:]+)(?::\s*(\S+))?"
)


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _is_graph_node(line: str) -> bool:
    stripped = line.lstrip("│|").lstrip()
    return stripped.startswith(("◉", "○", "◯", "◆", "●", "@", "*"))


def _extract_branch_name(line: str) -> str:
    match = _BRANCH_NAME_RE.search(line)
    return match.group(1) if match else ""


def _ok_confirmation(verb: str, detail: str) -> str:
    detail = detail.strip()
    return f"ok {verb} {detail}".strip()


def _filter_gt_log_entries(input_text: str) -> str:
    trimmed = input_text.strip()
    if not trimmed:
        return ""

    lines = trimmed.splitlines()
    result: list[str] = []
    entry_count = 0
    max_entries = 15

    for index, line in enumerate(lines):
        if _is_graph_node(line):
            entry_count += 1
        replaced = _EMAIL_RE.sub("", line).rstrip()
        result.append(_truncate(replaced, 120))
        if entry_count >= max_entries:
            remaining = sum(1 for other in lines[index + 1 :] if _is_graph_node(other))
            if remaining > 0:
                result.append(f"... +{remaining} more entries")
            break

    return "\n".join(result)


def _filter_gt_submit(input_text: str) -> str:
    trimmed = input_text.strip()
    if not trimmed:
        return ""

    pushed: list[str] = []
    prs: list[str] = []
    for line in trimmed.splitlines():
        line = line.strip()
        if not line:
            continue
        if "pushed" in line.lower():
            pushed.append(_extract_branch_name(line))
            continue
        match = _PR_LINE_RE.search(line)
        if not match:
            continue
        action = match.group(1).lower()
        number = match.group(2)
        branch = match.group(3)
        url = match.group(4)
        if url:
            prs.append(f"{action} PR #{number} {branch} {url}")
        else:
            prs.append(f"{action} PR #{number} {branch}")

    summary: list[str] = []
    branch_names = [name for name in pushed if name]
    if branch_names:
        summary.append(f"pushed {', '.join(branch_names)}")
    elif pushed:
        summary.append(f"pushed {len(pushed)} branches")
    summary.extend(prs)
    return "\n".join(summary) if summary else _truncate(trimmed)


def _filter_gt_sync(input_text: str) -> str:
    trimmed = input_text.strip()
    if not trimmed:
        return ""

    synced = 0
    deleted = 0
    deleted_names: list[str] = []
    for line in trimmed.splitlines():
        line = line.strip()
        if not line:
            continue
        lowered = line.lower()
        if ("synced" in lowered and "branch" in lowered) or line.startswith(
            "Synced with remote"
        ):
            synced += 1
        if "deleted" in lowered:
            deleted += 1
            name = _extract_branch_name(line)
            if name:
                deleted_names.append(name)

    parts: list[str] = []
    if synced > 0:
        parts.append(f"{synced} synced")
    if deleted > 0:
        if deleted_names:
            parts.append(f"{deleted} deleted ({', '.join(deleted_names)})")
        else:
            parts.append(f"{deleted} deleted")
    if not parts:
        return _ok_confirmation("sync:", "")
    return f"ok sync: {', '.join(parts)}"


def _filter_gt_restack(input_text: str) -> str:
    trimmed = input_text.strip()
    if not trimmed:
        return ""

    restacked = 0
    for line in trimmed.splitlines():
        line = line.strip()
        if ("Restacked" in line or "Rebased" in line) and "branch" in line:
            restacked += 1
    if restacked > 0:
        return _ok_confirmation("restacked", f"{restacked} branches")
    return _ok_confirmation("restacked", "")


def _filter_gt_create(input_text: str) -> str:
    trimmed = input_text.strip()
    if not trimmed:
        return ""

    branch_name = ""
    for line in trimmed.splitlines():
        line = line.strip()
        if "created" in line.lower():
            branch_name = _extract_branch_name(line)
            if branch_name:
                break
    if branch_name:
        return _ok_confirmation("created", branch_name)
    first_line = trimmed.splitlines()[0].strip()
    return _ok_confirmation("created", first_line)


def filter_gt_output(
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
    if lowered.startswith("gt log"):
        text = _filter_gt_log_entries(combined)
        filter_name = "gt.log"
    elif lowered.startswith("gt submit"):
        text = _filter_gt_submit(combined)
        filter_name = "gt.submit"
    elif lowered.startswith("gt sync"):
        text = _filter_gt_sync(combined)
        filter_name = "gt.sync"
    elif lowered.startswith("gt restack"):
        text = _filter_gt_restack(combined)
        filter_name = "gt.restack"
    elif lowered.startswith("gt create"):
        text = _filter_gt_create(combined)
        filter_name = "gt.create"
    elif lowered.startswith("gt branch"):
        text = combined.strip()
        filter_name = "gt.branch"
    else:
        text = generic.output
        filter_name = "gt"
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
