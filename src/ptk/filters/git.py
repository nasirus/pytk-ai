from __future__ import annotations

import re

from ..models import FilterResult
from .base import make_filter_result
from .generic import _combine_streams, filter_generic_output


def _drop_advice_lines(text: str) -> str:
    lines = [
        line for line in text.splitlines() if not line.lstrip().startswith('(use "git ')
    ]
    return "\n".join(lines)


def _git_subcommand(command: str) -> str | None:
    match = re.search(r"\bgit\s+(?:-[Cc]\s+\S+\s+)*([a-z]+)\b", command)
    return match.group(1) if match else None


def _compact_subject(lines: list[str]) -> str | None:
    for line in lines:
        if line.startswith("    "):
            subject = line.strip()
            if subject:
                return subject
    return None


def _summarize_log(text: str) -> str:
    lines = text.splitlines()
    commits: list[str] = []
    current_hash: str | None = None
    subject: str | None = None
    refs: str | None = None
    for line in lines:
        if line.startswith("commit "):
            if current_hash:
                summary = current_hash[:7]
                if refs:
                    summary += f" {refs}"
                if subject:
                    summary += f" {subject}"
                commits.append(summary)
            current_hash = line.split()[1]
            ref_match = re.search(r"\(([^)]+)\)", line)
            refs = ref_match.group(1) if ref_match else None
            subject = None
            continue
        if current_hash and subject is None and line.startswith("    "):
            stripped = line.strip()
            if stripped:
                subject = stripped
    if current_hash:
        summary = current_hash[:7]
        if refs:
            summary += f" {refs}"
        if subject:
            summary += f" {subject}"
        commits.append(summary)
    if commits:
        return "\n".join(commits)
    oneline = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[0-9a-f]{7,}\s+", stripped):
            oneline.append(stripped)
    return "\n".join(oneline) if oneline else text


def _parse_diff_summary(text: str, *, include_commit_header: bool = False) -> str:
    lines = text.splitlines()
    result: list[str] = []
    current_file: str | None = None
    added = 0
    removed = 0
    changes: list[str] = []
    commit_header: list[str] = []

    def flush_file() -> None:
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

    if include_commit_header:
        commit_hash = next(
            (line.split()[1][:7] for line in lines if line.startswith("commit ")),
            None,
        )
        subject = _compact_subject(lines)
        if commit_hash:
            header = f"commit {commit_hash}"
            if subject:
                header += f" {subject}"
            commit_header.append(header)

    for line in lines:
        if line.startswith("diff --git "):
            flush_file()
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[3].removeprefix("b/")
            continue
        if line.startswith(("index ", "@@ ", "--- ", "+++ ")):
            continue
        if current_file is None:
            stat_match = re.match(
                r"^\s*(.+?)\s+\|\s+\d+\s+[+\-]+$",
                line,
            )
            if stat_match:
                result.append(stat_match.group(1).strip())
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
            changes.append(f"  + {line[1:].strip()}")
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
            changes.append(f"  - {line[1:].strip()}")
    flush_file()
    if commit_header:
        return "\n".join(commit_header + result)
    return "\n".join(result) if result else text


def _summarize_branch(text: str) -> str:
    locals_: list[str] = []
    remotes: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if raw.startswith("*"):
            locals_.append(f"* {line[2:].strip()}")
        elif line.startswith("remotes/"):
            remotes.append(line)
        else:
            locals_.append(f"  {line}")
    if not locals_ and not remotes:
        return text
    result = locals_
    if remotes:
        result.append(f"remotes ({len(remotes)}):")
        result.extend(f"  {branch}" for branch in remotes[:8])
        if len(remotes) > 8:
            result.append(f"  ... +{len(remotes) - 8} more")
    return "\n".join(result)


def _summarize_commit(text: str) -> str:
    match = re.search(r"^\[(?:[^\]]+\s)?([0-9a-f]{7,})\]\s+(.+)$", text, re.MULTILINE)
    if match:
        return f"ok {match.group(1)[:7]} {match.group(2).strip()}"
    hash_match = re.search(r"^commit\s+([0-9a-f]{7,40})$", text, re.MULTILINE)
    subject = _compact_subject(text.splitlines())
    if hash_match:
        output = f"ok {hash_match.group(1)[:7]}"
        if subject:
            output += f" {subject}"
        return output
    return "ok"


def _summarize_push(text: str) -> str:
    if "Everything up-to-date" in text:
        return "ok up-to-date"
    target = None
    for line in text.splitlines():
        if "->" in line:
            target = line.split("->", 1)[1].strip()
    return f"ok {target}" if target else "ok"


def _summarize_pull(text: str) -> str:
    if "Already up to date." in text:
        return "ok up-to-date"
    match = re.search(
        r"(\d+)\s+files? changed(?:,\s+(\d+)\s+insertions?\(\+\))?(?:,\s+(\d+)\s+deletions?\(-\))?",
        text,
    )
    if match:
        files = match.group(1)
        insertions = match.group(2) or "0"
        deletions = match.group(3) or "0"
        return f"ok {files} files +{insertions} -{deletions}"
    return "ok"


def _summarize_fetch(text: str) -> str:
    ref_updates = sum(
        1
        for line in text.splitlines()
        if "->" in line or line.lstrip().startswith(("* [new", "+ "))
    )
    if ref_updates:
        return f"ok fetched ({ref_updates} refs)"
    return "ok"


def _summarize_stash(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "ok"
    if all(line.startswith("stash@{") for line in lines):
        return "\n".join(lines[:10])
    return lines[0]


def _summarize_worktree(text: str) -> str:
    result: list[str] = []
    for line in text.splitlines():
        match = re.match(
            r"^(?P<path>\S+)\s+(?P<hash>[0-9a-f]{7,40})\s+\[(?P<branch>[^\]]+)\]",
            line.strip(),
        )
        if not match:
            continue
        result.append(
            f"{match.group('branch')} {match.group('path')} {match.group('hash')[:7]}"
        )
    return "\n".join(result) if result else text


def filter_git_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    combined = _drop_advice_lines(_combine_streams(stdout, stderr, exit_code))
    generic = filter_generic_output(
        command,
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    subcommand = _git_subcommand(command)
    text = _drop_advice_lines(generic.output)
    filter_name = f"git.{subcommand}" if subcommand else "git"
    if exit_code != 0:
        return make_filter_result(
            combined,
            filter_name=filter_name,
            max_output_lines=max_output_lines,
            error=generic.error,
        )
    if subcommand == "status":
        text = text
    elif subcommand == "log":
        text = _summarize_log(combined)
    elif subcommand == "diff":
        text = _parse_diff_summary(combined)
    elif subcommand == "show":
        text = _parse_diff_summary(combined, include_commit_header=True)
    elif subcommand == "add":
        text = combined or "ok"
    elif subcommand == "commit":
        text = _summarize_commit(combined)
    elif subcommand == "push":
        text = _summarize_push(combined)
    elif subcommand == "pull":
        text = _summarize_pull(combined)
    elif subcommand == "branch":
        text = _summarize_branch(combined)
    elif subcommand == "fetch":
        text = _summarize_fetch(combined)
    elif subcommand == "stash":
        text = _summarize_stash(combined)
    elif subcommand == "worktree":
        text = _summarize_worktree(combined)
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
