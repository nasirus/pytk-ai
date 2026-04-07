from __future__ import annotations

from dataclasses import dataclass
import shlex
import textwrap
from typing import Callable


@dataclass(frozen=True)
class ExecutionRewriteContext:
    trimmed: str
    prefix: str
    normalized_command: str
    rest: str
    redirect_suffix: str
    filter_hint: str | None
    matched_rule: str | None


ExecutionRewriteHandler = Callable[[ExecutionRewriteContext], str | None]


_GIT_GLOBAL_FLAGS_WITH_VALUE = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--config-env",
}
_GIT_LOG_FORMAT = "%h %s (%ar) <%an>%n%b%n---END---"
_GIT_SHOW_SUMMARY_FORMAT = "%h %s (%ar) <%an>"
_GIT_SHOW_PASSTHROUGH_FLAGS = {"--stat", "--numstat", "--shortstat"}
_GIT_BRANCH_ACTION_FLAGS = {
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
_GIT_BRANCH_LIST_FLAGS = {
    "-a",
    "--all",
    "-r",
    "--remotes",
    "--list",
    "--merged",
    "--no-merged",
    "--contains",
    "--no-contains",
    "--format",
    "--sort",
    "--points-at",
}
_GIT_WORKTREE_ACTIONS = {"add", "remove", "prune", "lock", "unlock", "move"}
_GH_GLOBAL_FLAGS_WITH_VALUE = {"-R", "--repo", "--hostname"}
_GH_IDENTIFIER_FLAGS_WITH_VALUE = {
    "-R",
    "--repo",
    "-q",
    "--jq",
    "-t",
    "--template",
    "--job",
    "--attempt",
}
_GH_PR_LIST_FIELDS = "number,title,state,author,updatedAt"
_GH_PR_VIEW_FIELDS = (
    "number,title,state,author,body,url,mergeable,reviews,statusCheckRollup"
)
_GH_ISSUE_LIST_FIELDS = "number,title,state,author"
_GH_RUN_LIST_FIELDS = "databaseId,name,status,conclusion,createdAt"
_DIFF_UNIFIED_FLAGS = {"-u", "--unified"}
_FIND_SUPPORTED_FLAGS_WITH_VALUE = {"-name", "-iname", "-type", "-maxdepth"}
_FIND_UNSUPPORTED_FLAGS = {
    "-not",
    "!",
    "-or",
    "-o",
    "-and",
    "-a",
    "-exec",
    "-execdir",
    "-delete",
    "-print0",
    "-newer",
    "-perm",
    "-size",
    "-mtime",
    "-mmin",
    "-atime",
    "-amin",
    "-ctime",
    "-cmin",
    "-empty",
    "-link",
    "-regex",
    "-iregex",
}
_FIND_REWRITE_SCRIPT = textwrap.dedent(
    """
    import fnmatch
    import os
    import subprocess
    import sys

    path, pattern, file_type, max_depth_raw, case_insensitive = sys.argv[1:6]
    if not os.path.exists(path):
        sys.stderr.write(f"find: '{path}': No such file or directory\\n")
        raise SystemExit(1)

    max_depth = None if max_depth_raw == "" else int(max_depth_raw)
    want_dirs = file_type == "d"
    root = os.path.abspath(path)
    pattern_cmp = pattern.lower() if case_insensitive == "1" else pattern

    def _depth(rel_path):
        return 0 if rel_path in {"", "."} else rel_path.count(os.sep) + 1

    def _is_hidden_name(name):
        return name.startswith(".")

    def _has_hidden_part(rel_path):
        return any(
            part.startswith(".")
            for part in rel_path.split(os.sep)
            if part not in {"", "."}
        )

    def _normalize_rel_path(rel_path):
        return rel_path.replace(os.sep, "/")

    def _matches(name):
        candidate = name.lower() if case_insensitive == "1" else name
        return fnmatch.fnmatchcase(candidate, pattern_cmp)

    def _git_repo_root(start_path):
        base = start_path if os.path.isdir(start_path) else os.path.dirname(start_path)
        if not base:
            base = "."
        try:
            proc = subprocess.run(
                ["git", "-C", base, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        repo_root = proc.stdout.strip()
        return os.path.abspath(repo_root) if repo_root else None

    def _repo_rel_path(full_path, repo_root):
        rel_path = os.path.relpath(full_path, repo_root)
        if rel_path == "." or rel_path == ".." or rel_path.startswith(".." + os.sep):
            return None
        return rel_path

    def _git_check_ignored(repo_root, rel_paths):
        normalized = [
            _normalize_rel_path(rel_path)
            for rel_path in rel_paths
            if rel_path and rel_path != "."
        ]
        if not normalized:
            return set()
        try:
            proc = subprocess.run(
                ["git", "-C", repo_root, "check-ignore", "-z", "--stdin"],
                input="\\0".join(normalized) + "\\0",
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return set()
        if proc.returncode not in {0, 1}:
            return set()
        return {entry for entry in proc.stdout.split("\\0") if entry}

    def _visible_git_files(repo_root):
        repo_rel_root = _repo_rel_path(root, repo_root)
        args = ["git", "-C", repo_root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        if repo_rel_root is not None:
            args.extend(["--", _normalize_rel_path(repo_rel_root)])
        try:
            proc = subprocess.run(args, capture_output=True, check=False)
        except OSError:
            return None
        if proc.returncode != 0:
            return None

        results = []
        for raw_entry in proc.stdout.split(b"\\0"):
            if not raw_entry:
                continue
            repo_rel = raw_entry.decode("utf-8", errors="surrogateescape")
            full_path = os.path.join(repo_root, repo_rel)
            if not os.path.isfile(full_path):
                continue
            rel_path = os.path.relpath(full_path, root)
            if rel_path == "." or rel_path == ".." or rel_path.startswith(".." + os.sep):
                continue
            if _has_hidden_part(rel_path):
                continue
            if max_depth is not None and _depth(rel_path) > max_depth:
                continue
            if _matches(os.path.basename(full_path)):
                results.append(_normalize_rel_path(rel_path))
        return results

    repo_root = _git_repo_root(root)
    root_repo_rel = _repo_rel_path(root, repo_root) if repo_root else None
    if root_repo_rel and _normalize_rel_path(root_repo_rel) in _git_check_ignored(repo_root, [root_repo_rel]):
        raise SystemExit(0)

    results = []
    used_git_file_listing = False
    if not want_dirs and repo_root is not None:
        visible_files = _visible_git_files(repo_root)
        if visible_files is not None:
            results = visible_files
            used_git_file_listing = True
    if not used_git_file_listing:
        fallback_ignore_dirs = {
            "node_modules",
            "target",
            "dist",
            "build",
            ".next",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            ".mypy_cache",
            ".pytest_cache",
            ".idea",
            ".vscode",
            ".vs",
            ".cache",
            ".turbo",
            ".vercel",
            ".tox",
            ".nyc_output",
            ".eggs",
            "coverage",
            ".ruff_cache",
        }

        for current_root, dirnames, filenames in os.walk(root, topdown=True):
            rel_root = os.path.relpath(current_root, root)
            depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1

            visible_dirnames = [name for name in dirnames if not _is_hidden_name(name)]
            if repo_root is None:
                visible_dirnames = [
                    name for name in visible_dirnames if name not in fallback_ignore_dirs
                ]
            else:
                dir_rel_map = {
                    name: _repo_rel_path(os.path.join(current_root, name), repo_root)
                    for name in visible_dirnames
                }
                ignored_dirs = _git_check_ignored(
                    repo_root,
                    [rel_path for rel_path in dir_rel_map.values() if rel_path is not None],
                )
                visible_dirnames = [
                    name
                    for name in visible_dirnames
                    if (
                        dir_rel_map[name] is None
                        or _normalize_rel_path(dir_rel_map[name]) not in ignored_dirs
                    )
                ]

            dirnames[:] = visible_dirnames
            if max_depth is not None and depth >= max_depth:
                dirnames[:] = []

            if want_dirs:
                entries = [(name, os.path.join(current_root, name)) for name in dirnames]
            else:
                visible_filenames = [name for name in filenames if not _is_hidden_name(name)]
                if repo_root is not None:
                    file_rel_map = {
                        name: _repo_rel_path(os.path.join(current_root, name), repo_root)
                        for name in visible_filenames
                    }
                    ignored_files = _git_check_ignored(
                        repo_root,
                        [
                            rel_path
                            for rel_path in file_rel_map.values()
                            if rel_path is not None
                        ],
                    )
                    visible_filenames = [
                        name
                        for name in visible_filenames
                        if (
                            file_rel_map[name] is None
                            or _normalize_rel_path(file_rel_map[name]) not in ignored_files
                        )
                    ]
                entries = [
                    (name, os.path.join(current_root, name))
                    for name in visible_filenames
                ]

            for name, full_path in entries:
                if not _matches(name):
                    continue
                rel_path = os.path.relpath(full_path, root)
                if rel_path and rel_path != ".":
                    results.append(_normalize_rel_path(rel_path))

    results.sort()
    sys.stdout.write("\\n".join(results))
    if results:
        sys.stdout.write("\\n")
    """
).strip()


def _split_git_command(command: str) -> tuple[list[str], str | None, list[str]]:
    tokens = shlex.split(command)
    if not tokens or tokens[0] != "git":
        return [], None, []
    global_args: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            global_args.append(token)
            index += 1
            if index < len(tokens):
                global_args.append(tokens[index])
                index += 1
            continue
        if token.startswith("-"):
            global_args.append(token)
            index += 1
            continue
        break
    if index >= len(tokens):
        return global_args, None, []
    return global_args, tokens[index], tokens[index + 1 :]


def _join_git_command(global_args: list[str], subcommand: str, args: list[str]) -> str:
    return shlex.join(["git", *global_args, subcommand, *args])


def _split_gh_command(command: str) -> tuple[list[str], list[str]]:
    tokens = shlex.split(command)
    if not tokens or tokens[0] != "gh":
        return [], []
    global_args: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in _GH_GLOBAL_FLAGS_WITH_VALUE:
            global_args.append(token)
            index += 1
            if index < len(tokens):
                global_args.append(tokens[index])
                index += 1
            continue
        if token.startswith("-"):
            global_args.append(token)
            index += 1
            continue
        break
    return global_args, tokens[index:]


def _join_gh_command(global_args: list[str], args: list[str]) -> str:
    return shlex.join(["gh", *global_args, *args])


def _extract_gh_identifier_and_extra_args(
    args: list[str],
) -> tuple[str | None, list[str]]:
    identifier: str | None = None
    extra: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            extra.append(arg)
            skip_next = False
            continue
        if arg in _GH_IDENTIFIER_FLAGS_WITH_VALUE:
            extra.append(arg)
            skip_next = True
            continue
        if arg.startswith("-"):
            extra.append(arg)
            continue
        if identifier is None:
            identifier = arg
        else:
            extra.append(arg)
    return identifier, extra


def _rewrite_gh_execution(ctx: ExecutionRewriteContext) -> str | None:
    global_args, args = _split_gh_command(ctx.normalized_command)
    if len(args) < 2:
        return None

    rewritten_args: list[str] | None = None

    if args[:2] == ["pr", "list"]:
        rewritten_args = ["pr", "list", "--json", _GH_PR_LIST_FIELDS, *args[2:]]
    elif args[:2] == ["pr", "view"]:
        identifier, extra_args = _extract_gh_identifier_and_extra_args(args[2:])
        if identifier is None or any(
            arg in {"--web", "--comments"} for arg in extra_args
        ):
            return None
        rewritten_args = [
            "pr",
            "view",
            identifier,
            "--json",
            _GH_PR_VIEW_FIELDS,
            *extra_args,
        ]
    elif args[:2] == ["issue", "list"]:
        rewritten_args = [
            "issue",
            "list",
            "--json",
            _GH_ISSUE_LIST_FIELDS,
            *args[2:],
        ]
    elif args[:2] == ["run", "list"]:
        rewritten_args = [
            "run",
            "list",
            "--json",
            _GH_RUN_LIST_FIELDS,
            "--limit",
            "10",
            *args[2:],
        ]

    if rewritten_args is None:
        return None

    return f"{ctx.prefix}{_join_gh_command(global_args, rewritten_args)}{ctx.redirect_suffix}"


def _rewrite_golangci_execution(ctx: ExecutionRewriteContext) -> str | None:
    tokens = shlex.split(ctx.normalized_command)
    if not tokens or tokens[0] != "golangci-lint":
        return None
    if any(
        token == "--out-format"
        or token.startswith("--out-format=")
        or token == "--output.json.path"
        or token.startswith("--output.json.path=")
        for token in tokens[1:]
    ):
        return None
    args = tokens[1:]
    if args and args[0] == "run":
        run_args = args[1:]
    else:
        run_args = args
    v1_cmd = shlex.join(["golangci-lint", "run", "--out-format=json", *run_args])
    v2_cmd = shlex.join(
        ["golangci-lint", "run", "--output.json.path", "stdout", *run_args]
    )
    rewritten = (
        'version_output="$(golangci-lint --version 2>/dev/null || true)"; '
        'case "$version_output" in '
        '*" version 2."*|*" has version 2."*) '
        f"{v2_cmd} ;; "
        f"*) {v1_cmd} ;; "
        "esac"
    )
    return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"


def _rewrite_rspec_execution(ctx: ExecutionRewriteContext) -> str | None:
    tokens = shlex.split(ctx.normalized_command)
    if not tokens:
        return None
    command_index = None
    if (
        len(tokens) >= 3
        and tokens[:2] == ["bundle", "exec"]
        and tokens[2].endswith("rspec")
    ):
        command_index = 2
    elif tokens[0].endswith("rspec"):
        command_index = 0
    if command_index is None:
        return None
    args = tokens[command_index + 1 :]
    if any(
        arg == "--format"
        or arg == "-f"
        or arg.startswith("--format=")
        or (arg.startswith("-f") and len(arg) > 2 and not arg.startswith("--"))
        for arg in args
    ):
        return None
    rewritten = [*tokens[: command_index + 1], "--format", "json", *args]
    return f"{ctx.prefix}{shlex.join(rewritten)}{ctx.redirect_suffix}"


def _rewrite_rubocop_execution(ctx: ExecutionRewriteContext) -> str | None:
    tokens = shlex.split(ctx.normalized_command)
    if not tokens:
        return None
    command_index = None
    if (
        len(tokens) >= 3
        and tokens[:2] == ["bundle", "exec"]
        and tokens[2].endswith("rubocop")
    ):
        command_index = 2
    elif tokens[0].endswith("rubocop"):
        command_index = 0
    if command_index is None:
        return None
    args = tokens[command_index + 1 :]
    if any(arg in {"-a", "-A", "--auto-correct", "--auto-correct-all"} for arg in args):
        return None
    if any(
        arg == "--format"
        or arg == "-f"
        or arg.startswith("--format=")
        or (arg.startswith("-f") and len(arg) > 2 and not arg.startswith("--"))
        for arg in args
    ):
        return None
    rewritten = [*tokens[: command_index + 1], "--format", "json", *args]
    return f"{ctx.prefix}{shlex.join(rewritten)}{ctx.redirect_suffix}"


def _rewrite_git_log_execution(global_args: list[str], args: list[str]) -> str:
    has_format_flag = any(
        arg == "--oneline" or arg.startswith("--pretty") or arg.startswith("--format")
        for arg in args
    )
    has_limit_flag = any(
        (arg.startswith("-") and len(arg) > 1 and arg[1].isdigit())
        or arg == "-n"
        or arg.startswith("--max-count")
        for arg in args
    )
    wants_merges = any(arg in {"--merges", "--min-parents=2"} for arg in args)

    rewritten_args: list[str] = []
    if not has_format_flag:
        rewritten_args.append(f"--pretty=format:{_GIT_LOG_FORMAT}")
    if not has_limit_flag:
        rewritten_args.append("-50" if has_format_flag else "-10")
    if not wants_merges:
        rewritten_args.append("--no-merges")
    rewritten_args.extend(args)
    return _join_git_command(global_args, "log", rewritten_args)


def _rewrite_git_diff_execution(global_args: list[str], args: list[str]) -> str:
    passthrough = [arg for arg in args if arg != "--no-compact"]
    wants_passthrough = (
        any(arg in {"--stat", "--numstat", "--shortstat"} for arg in passthrough)
        or "--no-compact" in args
    )
    if wants_passthrough:
        return _join_git_command(global_args, "diff", passthrough)

    stat_cmd = _join_git_command(global_args, "diff", ["--stat", *args])
    diff_cmd = _join_git_command(global_args, "diff", args)
    return (
        f"{stat_cmd}; status=$?; if [ $status -ne 0 ]; then exit $status; fi; "
        f'diff_output="$({diff_cmd})"; status=$?; if [ $status -ne 0 ]; then '
        f'printf "%s" "$diff_output"; exit $status; fi; '
        f'if [ -n "$diff_output" ]; then printf "\\n--- Changes ---\\n%s\\n" "$diff_output"; fi'
    )


def _rewrite_git_show_execution(global_args: list[str], args: list[str]) -> str | None:
    wants_passthrough = any(arg in _GIT_SHOW_PASSTHROUGH_FLAGS for arg in args) or any(
        arg.startswith("--pretty") or arg.startswith("--format") for arg in args
    )
    wants_blob_show = any(not arg.startswith("-") and ":" in arg for arg in args)
    if wants_passthrough or wants_blob_show:
        return None

    summary_cmd = _join_git_command(
        global_args,
        "show",
        ["--no-patch", f"--pretty=format:{_GIT_SHOW_SUMMARY_FORMAT}", *args],
    )
    stat_cmd = _join_git_command(
        global_args,
        "show",
        ["--stat", "--pretty=format:", *args],
    )
    diff_cmd = _join_git_command(global_args, "show", ["--pretty=format:", *args])
    return (
        f'summary="$({summary_cmd})"; status=$?; if [ $status -ne 0 ]; then exit $status; fi; '
        f'printf "%s\\n" "$summary"; '
        f'stat_output="$({stat_cmd})"; status=$?; if [ $status -ne 0 ]; then '
        f'printf "%s" "$stat_output"; exit $status; fi; '
        f'if [ -n "$stat_output" ]; then printf "%s\\n" "$stat_output"; fi; '
        f'diff_output="$({diff_cmd})"; status=$?; if [ $status -ne 0 ]; then '
        f'printf "%s" "$diff_output"; exit $status; fi; '
        f'if [ -n "$diff_output" ]; then printf "\\n--- Changes ---\\n%s\\n" "$diff_output"; fi'
    )


def _rewrite_git_add_execution(global_args: list[str], args: list[str]) -> str:
    add_args = args or ["."]
    add_cmd = _join_git_command(global_args, "add", add_args)
    stat_cmd = _join_git_command(
        global_args, "diff", ["--cached", "--stat", "--shortstat"]
    )
    return (
        f"{add_cmd}; status=$?; if [ $status -ne 0 ]; then exit $status; fi; {stat_cmd}"
    )


def _rewrite_git_branch_execution(
    global_args: list[str], args: list[str]
) -> str | None:
    has_show_flag = any(arg == "--show-current" for arg in args)
    has_action_flag = any(
        arg in _GIT_BRANCH_ACTION_FLAGS
        or arg.startswith("--set-upstream-to=")
        or arg == "--set-upstream-to"
        for arg in args
    )
    has_list_flag = any(
        arg in _GIT_BRANCH_LIST_FLAGS
        or any(arg.startswith(f"{flag}=") for flag in _GIT_BRANCH_LIST_FLAGS)
        for arg in args
    )
    has_positional_arg = any(not arg.startswith("-") for arg in args)
    if has_show_flag or has_action_flag or (has_positional_arg and not has_list_flag):
        return None
    rewritten_args = ([] if has_list_flag else ["-a"]) + ["--no-color", *args]
    return _join_git_command(global_args, "branch", rewritten_args)


def _rewrite_git_stash_execution(global_args: list[str], args: list[str]) -> str | None:
    if not args or args[0] != "show" or "-p" in args:
        return None
    return _join_git_command(global_args, "stash", ["show", "-p", *args[1:]])


def _rewrite_git_worktree_execution(
    global_args: list[str], args: list[str]
) -> str | None:
    if not args:
        return _join_git_command(global_args, "worktree", ["list"])
    if args[0] in _GIT_WORKTREE_ACTIONS:
        return None
    return _join_git_command(global_args, "worktree", args)


def _rewrite_git_execution(ctx: ExecutionRewriteContext) -> str | None:
    global_args, subcommand, args = _split_git_command(ctx.normalized_command)
    if subcommand is None:
        return None
    if subcommand == "status" and not args:
        return (
            f"{ctx.prefix}"
            f"{_join_git_command(global_args, 'status', ['--porcelain=v1', '--branch'])}"
            f"{ctx.redirect_suffix}"
        )
    if subcommand == "log":
        return f"{ctx.prefix}{_rewrite_git_log_execution(global_args, args)}{ctx.redirect_suffix}"
    if subcommand == "diff":
        return f"{ctx.prefix}{_rewrite_git_diff_execution(global_args, args)}{ctx.redirect_suffix}"
    if subcommand == "show":
        rewritten = _rewrite_git_show_execution(global_args, args)
        if rewritten is not None:
            return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"
        return None
    if subcommand == "add":
        return f"{ctx.prefix}{_rewrite_git_add_execution(global_args, args)}{ctx.redirect_suffix}"
    if subcommand == "branch":
        rewritten = _rewrite_git_branch_execution(global_args, args)
        if rewritten is not None:
            return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"
        return None
    if subcommand == "stash":
        rewritten = _rewrite_git_stash_execution(global_args, args)
        if rewritten is not None:
            return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"
        return None
    if subcommand == "worktree":
        rewritten = _rewrite_git_worktree_execution(global_args, args)
        if rewritten is not None:
            return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"
        return None
    return None


def _rewrite_diff_execution(ctx: ExecutionRewriteContext) -> str | None:
    tokens = shlex.split(ctx.normalized_command)
    if not tokens or tokens[0] != "diff":
        return None
    args = tokens[1:]
    if not args or any(arg == "--" for arg in args):
        return None
    if any(arg in _DIFF_UNIFIED_FLAGS or arg.startswith("-U") for arg in args):
        return None
    if any(arg.startswith("-") for arg in args):
        return None
    if len(args) != 2:
        return None
    rewritten = shlex.join(["diff", "-u", *args])
    return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"


def _rewrite_find_execution(ctx: ExecutionRewriteContext) -> str | None:
    tokens = shlex.split(ctx.normalized_command)
    if not tokens or tokens[0] != "find":
        return None

    path = "."
    pattern = "*"
    file_type = "f"
    case_insensitive = False
    max_depth: int | None = None
    index = 1

    if index < len(tokens) and not tokens[index].startswith("-"):
        path = tokens[index]
        index += 1

    while index < len(tokens):
        token = tokens[index]
        if token in _FIND_UNSUPPORTED_FLAGS:
            return None
        if token in _FIND_SUPPORTED_FLAGS_WITH_VALUE:
            index += 1
            if index >= len(tokens):
                return None
            value = tokens[index]
            if token == "-name":
                pattern = value
            elif token == "-iname":
                pattern = value
                case_insensitive = True
            elif token == "-type":
                if value not in {"f", "d"}:
                    return None
                file_type = value
            elif token == "-maxdepth":
                try:
                    max_depth = int(value)
                except ValueError:
                    return None
        elif token.startswith("-"):
            return None
        else:
            return None
        index += 1

    rewritten = shlex.join(
        [
            "python3",
            "-c",
            _FIND_REWRITE_SCRIPT,
            path,
            pattern,
            file_type,
            "" if max_depth is None else str(max_depth),
            "1" if case_insensitive else "0",
        ]
    )
    return f"{ctx.prefix}{rewritten}{ctx.redirect_suffix}"


_HANDLERS: dict[str, tuple[ExecutionRewriteHandler, ...]] = {
    "diff": (_rewrite_diff_execution,),
    "find": (_rewrite_find_execution,),
    "gh": (_rewrite_gh_execution,),
    "git": (_rewrite_git_execution,),
    "golangci-lint": (_rewrite_golangci_execution,),
    "rspec": (_rewrite_rspec_execution,),
    "rubocop": (_rewrite_rubocop_execution,),
}


def rewrite_execution_command(ctx: ExecutionRewriteContext) -> str:
    if not ctx.filter_hint:
        return ctx.trimmed
    for handler in _HANDLERS.get(
        ctx.filter_hint, ()
    ):  # pragma: no branch - tiny registry
        rewritten = handler(ctx)
        if rewritten is not None:
            return rewritten
    return ctx.trimmed
