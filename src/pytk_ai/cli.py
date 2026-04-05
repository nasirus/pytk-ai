from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Any

from .rewrite import rewrite_command
from .runner import run_command


def _join_command(parts: list[str]) -> str:
    return shlex.join(parts).strip()


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
    )
    if result.filtered_output:
        sys.stdout.write(result.filtered_output)
        if not result.filtered_output.endswith("\n"):
            sys.stdout.write("\n")
    return result.exit_code


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
    parser = argparse.ArgumentParser(prog="pytk-ai", description="PYTK-AI command runner")
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
    run.set_defaults(func=_run_command)

    hook = sub.add_parser("hook", help="process hook JSON from stdin")
    hook_sub = hook.add_subparsers(dest="agent", required=True)
    for agent in ("claude", "cursor"):
        agent_parser = hook_sub.add_parser(agent)
        agent_parser.set_defaults(func=_run_hook)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
