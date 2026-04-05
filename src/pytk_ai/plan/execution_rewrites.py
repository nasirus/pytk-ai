from __future__ import annotations

from dataclasses import dataclass
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


def _rewrite_git_execution(ctx: ExecutionRewriteContext) -> str | None:
    if ctx.normalized_command != "git status":
        return None
    return f"{ctx.prefix}git status --porcelain=v1 --branch{ctx.redirect_suffix}"


_HANDLERS: dict[str, tuple[ExecutionRewriteHandler, ...]] = {
    "git": (_rewrite_git_execution,),
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
