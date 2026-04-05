from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .rewrite import rewrite_command, rewrite_exit_code


def _join_command(parts: list[str]) -> str:
    return " ".join(parts).strip()


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
            "permissionDecisionReason": "PTK auto-rewrite",
            "updatedInput": {"command": rewritten},
        }
    }
    sys.stdout.write(json.dumps(payload))


def _emit_cursor_hook(rewritten: str) -> None:
    payload = {"permission": "allow", "updated_input": {"command": rewritten}}
    sys.stdout.write(json.dumps(payload))


def _run_rewrite(args: argparse.Namespace) -> int:
    command = _join_command(args.args)
    code, rewritten = rewrite_exit_code(command, excluded=args.exclude or [])
    if code != 0 or not rewritten:
        return 1
    sys.stdout.write(rewritten)
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
    if result is None:
        if args.agent == "cursor":
            sys.stdout.write("{}")
        return 0

    if not result.changed:
        if args.agent == "cursor":
            sys.stdout.write("{}")
        return 0

    if args.agent == "cursor":
        _emit_cursor_hook(result.output)
    else:
        _emit_claude_hook(result.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ptk", description="PTK AI command rewriter")
    sub = parser.add_subparsers(dest="command", required=True)

    rewrite = sub.add_parser("rewrite", help="rewrite a raw shell command")
    rewrite.add_argument("args", nargs=argparse.REMAINDER, help="raw command tokens")
    rewrite.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="base commands to never rewrite",
    )
    rewrite.set_defaults(func=_run_rewrite)

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
