from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
from typing import Any

from .filters.files import render_read_output
from .rewrite import rewrite_command
from .runner import (
    run_command,
    run_deps_command,
    run_dotnet_command,
    run_env_command,
    run_err_command,
    run_format_command,
    run_gt_command,
    run_json_command,
    run_log_command,
    run_psql_command,
    run_smart_command,
    run_summary_command,
    run_test_command,
)


def _join_command(parts: list[str]) -> str:
    if parts and parts[0] == "--":
        parts = parts[1:]
    return shlex.join(parts).strip()


def _normalize_wrapper_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None or not argv:
        return argv

    known_option_values = {
        "run": {"--exclude", "--max-output-lines", "--usage-mode"},
        "test": {"--max-output-lines"},
        "err": {"--max-output-lines"},
        "dotnet": {"--max-output-lines"},
        "format": {"--max-output-lines"},
        "gt": {"--max-output-lines"},
        "summary": {"--max-output-lines"},
        "psql": {"--max-output-lines"},
    }
    subcommand = argv[0]
    if subcommand not in known_option_values:
        return argv

    normalized = [subcommand]
    index = 1
    expects_value_for = known_option_values[subcommand]
    while index < len(argv):
        token = argv[index]
        if token == "--":
            normalized.extend(argv[index:])
            return normalized
        if token in expects_value_for:
            normalized.append(token)
            index += 1
            if index < len(argv):
                normalized.append(argv[index])
                index += 1
            continue
        if any(token.startswith(f"{option}=") for option in expects_value_for):
            normalized.append(token)
            index += 1
            continue
        if token.startswith("-"):
            normalized.append("--")
            normalized.extend(argv[index:])
            return normalized
        normalized.extend(argv[index:])
        return normalized

    return normalized


def _read_stdin_json() -> dict[str, Any] | None:
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _hook_command_from_payload(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
    tool_args = payload.get("toolArgs")
    if isinstance(tool_args, str):
        try:
            parsed = json.loads(tool_args)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            command = parsed.get("command")
            if isinstance(command, str):
                return command
    return None


def _emit_claude_hook(rewritten: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "PYTK-AI auto-rewrite",
            "updatedInput": {"command": rewritten},
        }
    }
    sys.stdout.write(json.dumps(payload))


def _emit_cursor_hook(rewritten: str) -> None:
    payload = {"permission": "allow", "updated_input": {"command": rewritten}}
    sys.stdout.write(json.dumps(payload))


def _run_command(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_command(
        command,
        excluded=tuple(args.exclude or ()),
        max_output_lines=args.max_output_lines,
        usage_mode=args.usage_mode,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_test(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_test_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_err(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_err_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_format(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_format_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_dotnet(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_dotnet_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_gt(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_gt_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_json(args: argparse.Namespace) -> int:
    result = run_json_command(
        args.file,
        schema_only=args.schema,
        max_depth=args.max_depth,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    elif result.error:
        sys.stderr.write(f"{result.error}\n")
    return result.exit_code


def _run_log(args: argparse.Namespace) -> int:
    result = run_log_command(args.file)
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_env(args: argparse.Namespace) -> int:
    result = run_env_command(args.filter_text, show_all=args.all)
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_deps(args: argparse.Namespace) -> int:
    result = run_deps_command(args.path)
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_summary(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_summary_command(command)
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_smart(args: argparse.Namespace) -> int:
    result = run_smart_command(args.file)
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_psql(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    result = run_psql_command(
        command,
        max_output_lines=args.max_output_lines,
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


def _run_read(args: argparse.Namespace) -> int:
    if args.file == "-":
        content = sys.stdin.read()
        source_path = None
    else:
        try:
            content = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"pytk-ai read: {exc}\n")
            return 1

        source_path = args.file

    output = render_read_output(
        content,
        source_path=source_path,
        level=args.level,
        max_lines=args.max_lines,
        tail_lines=args.tail_lines,
        line_numbers=args.line_numbers,
    )
    if output:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _run_hook(args: argparse.Namespace) -> int:
    payload = _read_stdin_json()
    if not payload:
        if args.agent == "cursor":
            sys.stdout.write("{}")
        return 0

    command = _hook_command_from_payload(payload)
    if not command:
        if args.agent == "cursor":
            sys.stdout.write("{}")
        return 0

    result = rewrite_command(command)
    if result is None or not result.changed:
        if args.agent == "cursor":
            sys.stdout.write("{}")
        return 0

    if args.agent == "cursor":
        _emit_cursor_hook(result.output)
    else:
        _emit_claude_hook(result.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pytk-ai", description="PYTK-AI command runner"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute a raw shell command and filter output")
    run.add_argument("args", nargs=argparse.REMAINDER, help="raw command tokens")
    run.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="base commands to never plan as PYTK-AI-managed",
    )
    run.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    run.add_argument(
        "--usage-mode",
        choices=("interactive", "hook"),
        default="interactive",
        help="record whether filtering is being used directly or via a hook",
    )
    run.set_defaults(func=_run_command)

    test = sub.add_parser("test", help="execute a test command and keep failures only")
    test.add_argument("args", nargs=argparse.REMAINDER, help="raw test command tokens")
    test.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    test.set_defaults(func=_run_test)

    err = sub.add_parser("err", help="execute a command and keep errors/warnings only")
    err.add_argument("args", nargs=argparse.REMAINDER, help="raw command tokens")
    err.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    err.set_defaults(func=_run_err)

    format_parser = sub.add_parser(
        "format", help="execute a formatter command and keep compact output"
    )
    format_parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="formatter command tokens"
    )
    format_parser.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    format_parser.set_defaults(func=_run_format)

    dotnet = sub.add_parser("dotnet", help="execute dotnet and compact .NET output")
    dotnet.add_argument("args", nargs=argparse.REMAINDER, help="dotnet command tokens")
    dotnet.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    dotnet.set_defaults(func=_run_dotnet)

    gt = sub.add_parser("gt", help="execute Graphite commands and compact stack output")
    gt.add_argument("args", nargs=argparse.REMAINDER, help="gt command tokens")
    gt.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    gt.set_defaults(func=_run_gt)

    json_parser = sub.add_parser(
        "json", help="inspect JSON with compact or schema output"
    )
    json_parser.add_argument("file", help="JSON file path, or - for stdin")
    json_parser.add_argument(
        "--schema",
        action="store_true",
        help="show schema only, not values",
    )
    json_parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="maximum JSON traversal depth",
    )
    json_parser.set_defaults(func=_run_json)

    log_parser = sub.add_parser("log", help="deduplicate repeated log lines")
    log_parser.add_argument("file", help="log file path")
    log_parser.set_defaults(func=_run_log)

    env_parser = sub.add_parser("env", help="show filtered environment variables")
    env_parser.add_argument("filter_text", nargs="?", help="optional substring filter")
    env_parser.add_argument(
        "--all",
        action="store_true",
        help="show sensitive values without masking",
    )
    env_parser.set_defaults(func=_run_env)

    deps_parser = sub.add_parser(
        "deps", help="summarize dependency manifests in a directory"
    )
    deps_parser.add_argument(
        "path", nargs="?", default=".", help="project directory or manifest path"
    )
    deps_parser.set_defaults(func=_run_deps)

    summary_parser = sub.add_parser(
        "summary", help="execute a command and produce a heuristic summary"
    )
    summary_parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="raw command tokens"
    )
    summary_parser.set_defaults(func=_run_summary)

    smart_parser = sub.add_parser(
        "smart", help="summarize a source file heuristically without a model"
    )
    smart_parser.add_argument("file", help="source file path")
    smart_parser.set_defaults(func=_run_smart)

    psql = sub.add_parser("psql", help="execute psql and compact tabular output")
    psql.add_argument("args", nargs=argparse.REMAINDER, help="psql command tokens")
    psql.add_argument(
        "--max-output-lines",
        type=int,
        default=200,
        help="maximum number of filtered output lines",
    )
    psql.set_defaults(func=_run_psql)

    read = sub.add_parser("read", help="read a file with optional filtering")
    read.add_argument("file", help="file path to read, or - for stdin")
    read.add_argument(
        "-l",
        "--level",
        choices=("none", "minimal", "aggressive"),
        default="none",
        help="filter level for source-aware reads",
    )
    read.add_argument(
        "-m",
        "--max-lines",
        type=int,
        help="keep a structure-aware max line window",
    )
    read.add_argument(
        "--tail-lines",
        type=int,
        help="keep only the last N lines",
    )
    read.add_argument(
        "-n",
        "--line-numbers",
        action="store_true",
        help="show line numbers",
    )
    read.set_defaults(func=_run_read)

    hook = sub.add_parser("hook", help="process hook JSON from stdin")
    hook_sub = hook.add_subparsers(dest="agent", required=True)
    for agent in ("claude", "cursor"):
        agent_parser = hook_sub.add_parser(agent)
        agent_parser.set_defaults(func=_run_hook)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalize_wrapper_argv(argv))
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
