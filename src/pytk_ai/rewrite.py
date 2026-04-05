from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .plan import load_rules, plan_command


@dataclass(frozen=True)
class RewriteResult:
    output: str
    matched: bool
    changed: bool


def rewrite_command(
    cmd: str, excluded: Sequence[str] | None = None
) -> RewriteResult | None:
    plan = plan_command(cmd, excluded=excluded)
    if not cmd.strip() or (not plan.managed and not plan.changed):
        return None
    return RewriteResult(
        output=plan.planned_command,
        matched=plan.managed or plan.changed,
        changed=plan.changed,
    )


def rewrite_exit_code(
    cmd: str, excluded: Sequence[str] | None = None
) -> tuple[int, str | None]:
    result = rewrite_command(cmd, excluded=excluded)
    if result is None:
        return 1, None
    return 0, result.output


def summarize_rewrite(result: RewriteResult | None) -> str:
    if result is None:
        return ""
    return result.output


__all__ = [
    "RewriteResult",
    "load_rules",
    "rewrite_command",
    "rewrite_exit_code",
    "summarize_rewrite",
]
