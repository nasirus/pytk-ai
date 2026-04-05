from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    pattern: str
    ptk_cmd: str
    rewrite_prefixes: tuple[str, ...]
    category: str
    savings_pct: float


@dataclass(frozen=True)
class PlanSegment:
    original: str
    planned_command: str
    execution_command: str
    normalized_command: str
    operator: str | None = None
    managed: bool = False
    changed: bool = False
    filter_hint: str | None = None
    matched_rule: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class CommandPlan:
    original_command: str
    planned_command: str
    execution_command: str
    normalized_command: str
    segments: tuple[PlanSegment, ...] = ()
    managed: bool = False
    changed: bool = False
    filter_hint: str | None = None
    skip_reason: str | None = None
