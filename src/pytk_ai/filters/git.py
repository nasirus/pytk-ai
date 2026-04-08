from __future__ import annotations

import re
import shlex

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


def _git_args(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    if not tokens or tokens[0] != "git":
        return []
    index = 1
    flags_with_value = {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--super-prefix",
        "--config-env",
    }
    while index < len(tokens):
        token = tokens[index]
        if token in flags_with_value:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    return tokens[index:]


def _git_subcommand_args(command: str) -> list[str]:
    args = _git_args(command)
    return args[1:] if len(args) >= 2 else []


def _compact_subject(lines: list[str]) -> str | None:
    for line in lines:
        if line.startswith("    "):
            subject = line.strip()
            if subject:
                return subject
    return None


def _summarize_log(text: str) -> str:
    if "---END---" in text:
        commits: list[str] = []
        for block in text.split("---END---"):
            lines = [line.rstrip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            header = lines[0].strip()
            body = [line.strip() for line in lines[1:] if line.strip()][:3]
            commits.append("\n".join([header, *[f"  {line}" for line in body]]))
        if commits:
            return "\n".join(commits)

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


def _summarize_show(text: str) -> str:
    lines = text.splitlines()
    summary_prefix: list[str] = []
    diff_start = next(
        (index for index, line in enumerate(lines) if line.startswith("diff --git ")),
        None,
    )
    if diff_start is not None:
        prefix_lines = [line.rstrip() for line in lines[:diff_start] if line.strip()]
        if prefix_lines:
            summary_prefix.extend(prefix_lines)
        diff_summary = _parse_diff_summary("\n".join(lines[diff_start:]))
        return (
            "\n".join(summary_prefix + [diff_summary])
            if summary_prefix
            else diff_summary
        )
    return _parse_diff_summary(text, include_commit_header=True)


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


def _summarize_branch_verbose(text: str) -> str:
    result: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        match = re.match(
            r"^(?P<current>\*?)\s*(?P<branch>\S+)\s+(?P<hash>[0-9a-f]{7,40})(?:\s+(?P<tracking>\[[^\]]+\]))?",
            line,
        )
        if not match:
            result.append(line.strip())
            continue
        prefix = "* " if match.group("current") == "*" else "  "
        summary = f"{prefix}{match.group('branch')} {match.group('hash')[:7]}"
        tracking = match.group("tracking")
        if tracking:
            summary += f" {tracking}"
        result.append(summary)
    return "\n".join(result) if result else text


def _summarize_branch_list(text: str) -> str:
    current = ""
    local: list[str] = []
    remote: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if raw.startswith("* "):
            current = line[2:].strip()
        elif line.startswith("remotes/origin/"):
            branch = line.removeprefix("remotes/origin/")
            if branch.startswith("HEAD "):
                continue
            remote.append(branch)
        else:
            local.append(line)

    if not current and not local and not remote:
        return text

    result: list[str] = [f"* {current}" if current else "*"]
    result.extend(f"  {branch}" for branch in local)

    remote_only = [
        branch for branch in remote if branch != current and branch not in local
    ]
    if remote_only:
        result.append(f"  remote-only ({len(remote_only)}):")
        result.extend(f"    {branch}" for branch in remote_only[:10])
        if len(remote_only) > 10:
            result.append(f"    ... +{len(remote_only) - 10} more")
    return "\n".join(result)


def _summarize_commit(text: str) -> str:
    match = re.search(r"^\[(?:[^\]]+\s)?([0-9a-f]{7,})\]\s+(.+)$", text, re.MULTILINE)
    if match:
        return f"ok {match.group(1)[:7]}"
    hash_match = re.search(r"^commit\s+([0-9a-f]{7,40})$", text, re.MULTILINE)
    if hash_match:
        return f"ok {hash_match.group(1)[:7]}"
    return "ok"


def _summarize_push(text: str) -> str:
    if "Everything up-to-date" in text:
        return "ok (up-to-date)"
    target = None
    for line in text.splitlines():
        if "->" in line:
            target = line.split("->", 1)[1].strip()
    return f"ok {target}" if target else "ok"


def _summarize_pull(text: str) -> str:
    if "Already up to date." in text:
        return "ok (up-to-date)"
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


def _summarize_stash_list(text: str) -> str:
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ": " not in stripped:
            result.append(stripped)
            continue
        index, rest = stripped.split(": ", 1)
        if ": " in rest:
            _, message = rest.split(": ", 1)
            result.append(f"{index}: {message.strip()}")
        else:
            result.append(stripped)
    return "\n".join(result) if result else "No stashes"


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


def _summarize_add(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "ok (nothing to add)"
    warnings = [
        line for line in lines if line.startswith(("warning:", "hint:", "error:"))
    ]
    short = next(
        (
            line
            for line in reversed(lines)
            if "file changed" in line or "insertion" in line or "deletion" in line
        ),
        "",
    )
    if short and warnings:
        return "\n".join([f"ok {short}", *warnings])
    if short:
        return f"ok {short}"
    return "\n".join(["ok", *warnings]) if warnings else "\n".join(["ok", *lines])


def _human_status_branch_summary(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("On branch "):
            return f"* {stripped.removeprefix('On branch ').strip()}"
        if stripped.startswith("HEAD detached "):
            return f"* {stripped}"
        if stripped == "Not currently on any branch.":
            return f"* {stripped}"
    return None


def _summarize_status(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "clean"
    raw = "\n".join(lines)

    def render_status(
        branch_summary: str,
        staged: list[str],
        modified: list[str],
        untracked: list[str],
        conflicts: int,
    ) -> str:
        result = [branch_summary]
        sections = (
            ("+ Staged", staged),
            ("~ Modified", modified),
            ("? Untracked", untracked),
        )
        for header, items in sections:
            if not items:
                continue
            result.append(f"{header}: {len(items)} files")
            for item in items:
                result.append(f"   {item}")
        if conflicts:
            result.append(f"conflicts: {conflicts} files")
        if len(result) == 1:
            result.append("clean - nothing to commit")
        summary = "\n".join(result)
        return summary if len(summary) < len(raw) else raw

    if not lines[0].startswith("## "):
        branch_summary = _human_status_branch_summary(lines)
        if branch_summary is None:
            return raw
        staged: list[str] = []
        modified: list[str] = []
        untracked: list[str] = []
        conflicts = 0
        section: str | None = None

        for line in lines:
            stripped = line.strip()
            if stripped == "Changes to be committed:":
                section = "staged"
                continue
            if stripped == "Changes not staged for commit:":
                section = "modified"
                continue
            if stripped == "Untracked files:":
                section = "untracked"
                continue
            if stripped == "Unmerged paths:":
                section = "conflicts"
                continue
            if stripped.startswith(
                (
                    "On branch ",
                    "Your branch ",
                    "nothing ",
                    "HEAD detached ",
                    "Not currently on any branch.",
                )
            ):
                continue
            if not stripped or stripped.startswith("("):
                continue

            entry = stripped
            if ":" in stripped:
                _, _, entry = stripped.partition(":")
                entry = entry.strip()

            if section == "staged":
                staged.append(entry)
            elif section == "modified":
                modified.append(entry)
            elif section == "untracked":
                untracked.append(entry)
            elif section == "conflicts":
                conflicts += 1

        return render_status(
            branch_summary,
            staged,
            modified,
            untracked,
            conflicts,
        )

    branch_line = lines[0][3:]
    lines = lines[1:]
    staged: list[str] = []
    modified: list[str] = []
    untracked: list[str] = []
    conflicts = 0

    for line in lines:
        if line == "??":
            continue
        if line.startswith("?? "):
            untracked.append(line[3:])
            continue
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:]
        if "U" in status or status in {"AA", "DD"}:
            conflicts += 1
            continue
        if status[0] in {"M", "A", "C", "D", "R"}:
            staged.append(path)

        if status[1] == "M":
            modified.append(path)
        elif status[1] == "D":
            modified.append(path)

    return render_status(
        f"* {branch_line}",
        staged,
        modified,
        untracked,
        conflicts,
    )


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
    subcommand_args = _git_subcommand_args(command)
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
        text = _summarize_status(combined)
    elif subcommand == "log":
        text = _summarize_log(combined)
    elif subcommand == "diff":
        text = _parse_diff_summary(combined)
    elif subcommand == "show":
        text = _summarize_show(combined)
    elif subcommand == "add":
        text = _summarize_add(combined)
    elif subcommand == "commit":
        text = _summarize_commit(combined)
    elif subcommand == "push":
        text = _summarize_push(combined)
    elif subcommand == "pull":
        text = _summarize_pull(combined)
    elif subcommand == "branch":
        if any(arg == "--show-current" for arg in subcommand_args):
            text = combined.strip() or "ok"
        elif any(arg in {"-v", "-vv"} for arg in subcommand_args):
            text = _summarize_branch_verbose(combined)
        elif any(not arg.startswith("-") for arg in subcommand_args) and not any(
            arg in {"-a", "--all", "-r", "--remotes", "--list"}
            or arg.startswith("--format")
            or arg.startswith("--sort")
            or arg.startswith("--points-at")
            for arg in subcommand_args
        ):
            text = "ok"
        elif any(
            arg
            in {
                "-d",
                "-D",
                "-m",
                "-M",
                "-c",
                "-C",
                "-u",
                "--unset-upstream",
                "--edit-description",
            }
            or arg == "--set-upstream-to"
            or arg.startswith("--set-upstream-to=")
            for arg in subcommand_args
        ):
            text = "ok"
        elif (
            any(arg in {"-a", "--all"} for arg in subcommand_args)
            or not subcommand_args
        ):
            text = _summarize_branch_list(combined)
        else:
            text = _summarize_branch(combined)
    elif subcommand == "fetch":
        text = _summarize_fetch(combined)
    elif subcommand == "stash":
        if subcommand_args[:1] == ["list"]:
            text = _summarize_stash_list(combined)
        elif subcommand_args[:1] == ["show"]:
            text = _parse_diff_summary(combined)
        elif subcommand_args[:1] in (["pop"], ["apply"], ["drop"], ["push"]):
            text = f"ok stash {subcommand_args[0]}"
        elif not subcommand_args:
            text = (
                "ok (nothing to stash)"
                if "No local changes" in combined
                else "ok stashed"
            )
        else:
            text = _summarize_stash(combined)
    elif subcommand == "worktree":
        if subcommand_args[:1] and subcommand_args[0] in {
            "add",
            "remove",
            "prune",
            "lock",
            "unlock",
            "move",
        }:
            text = "ok"
        else:
            text = _summarize_worktree(combined)
    return make_filter_result(
        text,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
