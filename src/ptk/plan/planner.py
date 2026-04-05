from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from .models import CommandPlan, PlanSegment
from .normalize import (
    has_disabled_prefix,
    infer_filter_hint,
    normalize_absolute_first_token,
    rewrite_line_range,
    strip_env_prefix,
    strip_trailing_redirect_suffix,
    strip_word_prefix,
)
from .rules import match_rule, rule_filter_hint
from .scanner import scan_compound


def _raw_segment(
    segment: str,
    *,
    operator: str | None = None,
    skip_reason: str | None = None,
) -> PlanSegment:
    return PlanSegment(
        original=segment,
        planned_command=segment,
        execution_command=segment,
        normalized_command=segment,
        operator=operator,
        managed=False,
        changed=False,
        filter_hint=infer_filter_hint(segment),
        skip_reason=skip_reason,
    )


def _managed_segment(
    segment: str,
    *,
    planned_command: str,
    normalized_command: str,
    filter_hint: str | None,
    matched_rule: str | None,
    operator: str | None = None,
) -> PlanSegment:
    return PlanSegment(
        original=segment,
        planned_command=planned_command,
        execution_command=segment,
        normalized_command=normalized_command,
        operator=operator,
        managed=True,
        changed=planned_command != segment,
        filter_hint=filter_hint,
        matched_rule=matched_rule,
    )


def _plan_segment(segment: str, excluded: Sequence[str] = ()) -> PlanSegment | None:
    trimmed = segment.strip()
    if not trimmed:
        return None

    command_part, redirect_suffix = strip_trailing_redirect_suffix(trimmed)

    if command_part.startswith("ptk ") or command_part == "ptk":
        return _managed_segment(
            trimmed,
            planned_command=trimmed,
            normalized_command=command_part,
            filter_hint=infer_filter_hint(command_part),
            matched_rule="already-ptk",
        )

    if command_part.startswith("head -") or command_part.startswith("tail "):
        rewritten = rewrite_line_range(command_part, redirect_suffix)
        if rewritten is not None:
            return _managed_segment(
                trimmed,
                planned_command=rewritten,
                normalized_command=command_part,
                filter_hint="read",
                matched_rule="line-range",
            )
        return _raw_segment(trimmed, skip_reason="unsupported-line-range")

    if command_part.startswith("cat "):
        args = command_part[len("cat ") :].lstrip()
        if args.startswith("-") and not (args.startswith("-n ") or args == "-n"):
            return _raw_segment(trimmed, skip_reason="unsupported-cat-option")

    prefix, command_clean = strip_env_prefix(command_part)
    if has_disabled_prefix(prefix + command_clean):
        return _raw_segment(trimmed, skip_reason="disabled")

    normalized_command = normalize_absolute_first_token(command_clean)
    rule = match_rule(normalized_command)
    if rule is None:
        return _raw_segment(trimmed, skip_reason="unsupported-command")

    base = normalized_command.split(maxsplit=1)[0] if normalized_command else ""
    if base and base in excluded:
        return _raw_segment(trimmed, skip_reason="excluded-command")

    if rule.ptk_cmd == "ptk gh":
        lowered = normalized_command.lower()
        if any(flag in lowered for flag in ("--json", "--jq", "--template")):
            return _raw_segment(trimmed, skip_reason="gh-structured-output")

    for rewrite_prefix in rule.rewrite_prefixes:
        rest = strip_word_prefix(normalized_command, rewrite_prefix)
        if rest is None:
            continue
        rewritten = f"{prefix}{rule.ptk_cmd}"
        if rest:
            rewritten += f" {rest}"
        rewritten += redirect_suffix
        return _managed_segment(
            trimmed,
            planned_command=rewritten,
            normalized_command=normalized_command,
            filter_hint=rule_filter_hint(rule),
            matched_rule=rule.ptk_cmd,
        )

    return _raw_segment(trimmed, skip_reason="no-prefix-match")


def _join_segments(segments: Sequence[PlanSegment]) -> str:
    parts: list[str] = []
    for segment in segments:
        parts.append(segment.planned_command)
        if segment.operator is not None:
            parts.append(f" {segment.operator} ")
    return "".join(parts).strip()


def _command_plan(
    command: str,
    *,
    planned_command: str,
    segments: tuple[PlanSegment, ...],
    managed: bool,
    changed: bool,
    filter_hint: str | None,
    skip_reason: str | None = None,
) -> CommandPlan:
    normalized_command = next(
        (
            segment.normalized_command
            for segment in segments
            if segment.normalized_command
        ),
        command,
    )
    return CommandPlan(
        original_command=command,
        planned_command=planned_command,
        execution_command=command,
        normalized_command=normalized_command,
        segments=segments,
        managed=managed,
        changed=changed,
        filter_hint=filter_hint,
        skip_reason=skip_reason,
    )


def plan_command(command: str, excluded: Sequence[str] | None = None) -> CommandPlan:
    excluded = tuple(excluded or ())
    trimmed = command.strip()
    if not trimmed:
        return CommandPlan(
            original_command=command,
            planned_command="",
            execution_command="",
            normalized_command="",
            skip_reason="empty-command",
        )

    if "<<" in trimmed or "$((" in trimmed:
        return _command_plan(
            trimmed,
            planned_command=trimmed,
            segments=(
                _raw_segment(trimmed, skip_reason="unsupported-shell-construct"),
            ),
            managed=False,
            changed=False,
            filter_hint=infer_filter_hint(trimmed),
            skip_reason="unsupported-shell-construct",
        )

    segments, pipe_remainder = scan_compound(trimmed)
    if pipe_remainder is not None:
        left, operator = segments[-1]
        if left.startswith(("find ", "fd ")) or left in {"find", "fd"}:
            return _command_plan(
                trimmed,
                planned_command=trimmed,
                segments=(
                    _raw_segment(
                        left, operator=operator, skip_reason="unsupported-pipe-source"
                    ),
                    _raw_segment(pipe_remainder, skip_reason="pipe-remainder"),
                ),
                managed=False,
                changed=False,
                filter_hint=infer_filter_hint(trimmed),
                skip_reason="unsupported-pipe-source",
            )
        left_plan = _plan_segment(left, excluded)
        if left_plan is None or operator != "|":
            return _command_plan(
                trimmed,
                planned_command=trimmed,
                segments=(_raw_segment(trimmed, skip_reason="unsupported-pipe"),),
                managed=False,
                changed=False,
                filter_hint=infer_filter_hint(trimmed),
                skip_reason="unsupported-pipe",
            )
        left_plan = replace(left_plan, operator="|")
        right_plan = _raw_segment(pipe_remainder, skip_reason="pipe-remainder")
        planned_command = f"{left_plan.planned_command} | {pipe_remainder}"
        return _command_plan(
            trimmed,
            planned_command=planned_command,
            segments=(left_plan, right_plan),
            managed=left_plan.managed,
            changed=planned_command != trimmed,
            filter_hint=left_plan.filter_hint,
            skip_reason=None if left_plan.managed else left_plan.skip_reason,
        )

    planned_segments: list[PlanSegment] = []
    for segment, operator in segments:
        planned = _plan_segment(segment, excluded)
        if planned is None:
            continue
        planned_segments.append(replace(planned, operator=operator))

    if not planned_segments:
        return CommandPlan(
            original_command=trimmed,
            planned_command=trimmed,
            execution_command=trimmed,
            normalized_command=trimmed,
            skip_reason="empty-plan",
        )

    planned_command = _join_segments(planned_segments)
    managed = any(segment.managed for segment in planned_segments)
    changed = planned_command != trimmed
    filter_hint = next(
        (segment.filter_hint for segment in planned_segments if segment.filter_hint),
        infer_filter_hint(trimmed),
    )
    skip_reason = (
        None
        if managed
        else next(
            (
                segment.skip_reason
                for segment in planned_segments
                if segment.skip_reason
            ),
            None,
        )
    )
    return _command_plan(
        trimmed,
        planned_command=planned_command,
        segments=tuple(planned_segments),
        managed=managed,
        changed=changed,
        filter_hint=filter_hint,
        skip_reason=skip_reason,
    )
