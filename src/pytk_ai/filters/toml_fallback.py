from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback path
    tomllib = None

from .base import strip_ansi


_RTK_FILTERS_DIR = Path(__file__).resolve().parents[3] / "rtk" / "src" / "filters"


@dataclass(frozen=True)
class ReplaceRule:
    pattern: re.Pattern[str]
    replacement: str


@dataclass(frozen=True)
class MatchOutputRule:
    pattern: re.Pattern[str]
    message: str
    unless: re.Pattern[str] | None = None


@dataclass(frozen=True)
class FallbackFilter:
    name: str
    match_command: re.Pattern[str]
    strip_ansi: bool = False
    replace: tuple[ReplaceRule, ...] = ()
    match_output: tuple[MatchOutputRule, ...] = ()
    strip_lines_matching: tuple[re.Pattern[str], ...] = ()
    keep_lines_matching: tuple[re.Pattern[str], ...] = ()
    truncate_lines_at: int | None = None
    head_lines: int | None = None
    tail_lines: int | None = None
    max_lines: int | None = None
    on_empty: str | None = None


def _compile_patterns(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


def _compile_replace_rules(defn: dict[str, object]) -> tuple[ReplaceRule, ...]:
    rules: list[ReplaceRule] = []
    for rule in defn.get("replace", []):
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        if not isinstance(pattern, str) or not isinstance(replacement, str):
            continue
        rules.append(ReplaceRule(pattern=re.compile(pattern), replacement=replacement))
    return tuple(rules)


def _compile_match_output_rules(defn: dict[str, object]) -> tuple[MatchOutputRule, ...]:
    rules: list[MatchOutputRule] = []
    for rule in defn.get("match_output", []):
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("pattern")
        message = rule.get("message")
        unless = rule.get("unless")
        if not isinstance(pattern, str) or not isinstance(message, str):
            continue
        unless_pattern = re.compile(unless) if isinstance(unless, str) else None
        rules.append(
            MatchOutputRule(
                pattern=re.compile(pattern),
                message=message,
                unless=unless_pattern,
            )
        )
    return tuple(rules)


def _compile_filter(name: str, defn: dict[str, object]) -> FallbackFilter | None:
    match_command = defn.get("match_command")
    if not isinstance(match_command, str):
        return None

    strip_lines_matching = defn.get("strip_lines_matching", [])
    keep_lines_matching = defn.get("keep_lines_matching", [])
    if strip_lines_matching and keep_lines_matching:
        return None
    if not isinstance(strip_lines_matching, list) or not isinstance(
        keep_lines_matching, list
    ):
        return None

    try:
        return FallbackFilter(
            name=name,
            match_command=re.compile(match_command),
            strip_ansi=bool(defn.get("strip_ansi", False)),
            replace=_compile_replace_rules(defn),
            match_output=_compile_match_output_rules(defn),
            strip_lines_matching=_compile_patterns(strip_lines_matching),
            keep_lines_matching=_compile_patterns(keep_lines_matching),
            truncate_lines_at=_int_or_none(defn.get("truncate_lines_at")),
            head_lines=_int_or_none(defn.get("head_lines")),
            tail_lines=_int_or_none(defn.get("tail_lines")),
            max_lines=_int_or_none(defn.get("max_lines")),
            on_empty=defn.get("on_empty")
            if isinstance(defn.get("on_empty"), str)
            else None,
        )
    except re.error:
        return None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


@lru_cache(maxsize=1)
def load_builtin_filters() -> tuple[FallbackFilter, ...]:
    if tomllib is None or not _RTK_FILTERS_DIR.is_dir():
        return ()

    filters: list[FallbackFilter] = []
    for path in sorted(_RTK_FILTERS_DIR.glob("*.toml")):
        try:
            with path.open("rb") as handle:
                parsed = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            continue

        definitions = parsed.get("filters", {})
        if not isinstance(definitions, dict):
            continue
        for name, defn in definitions.items():
            if not isinstance(name, str) or not isinstance(defn, dict):
                continue
            compiled = _compile_filter(name, defn)
            if compiled is not None:
                filters.append(compiled)
    return tuple(filters)


def find_fallback_filter(command: str) -> FallbackFilter | None:
    for fallback_filter in load_builtin_filters():
        if fallback_filter.match_command.search(command):
            return fallback_filter
    return None


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len < 3:
        return "..."
    return f"{text[: max_len - 3]}..."


def apply_fallback_filter(fallback_filter: FallbackFilter, text: str) -> str:
    lines = text.splitlines()

    if fallback_filter.strip_ansi:
        lines = [strip_ansi(line) for line in lines]

    if fallback_filter.replace:
        updated_lines: list[str] = []
        for line in lines:
            for rule in fallback_filter.replace:
                line = rule.pattern.sub(rule.replacement, line)
            updated_lines.append(line)
        lines = updated_lines

    if fallback_filter.match_output:
        blob = "\n".join(lines)
        for rule in fallback_filter.match_output:
            if not rule.pattern.search(blob):
                continue
            if rule.unless is not None and rule.unless.search(blob):
                continue
            return rule.message

    if fallback_filter.strip_lines_matching:
        lines = [
            line
            for line in lines
            if not any(
                pattern.search(line) for pattern in fallback_filter.strip_lines_matching
            )
        ]
    elif fallback_filter.keep_lines_matching:
        lines = [
            line
            for line in lines
            if any(
                pattern.search(line) for pattern in fallback_filter.keep_lines_matching
            )
        ]

    if fallback_filter.truncate_lines_at is not None:
        lines = [
            _truncate_text(line, fallback_filter.truncate_lines_at) for line in lines
        ]

    total = len(lines)
    if (
        fallback_filter.head_lines is not None
        and fallback_filter.tail_lines is not None
        and total > fallback_filter.head_lines + fallback_filter.tail_lines
    ):
        head = fallback_filter.head_lines
        tail = fallback_filter.tail_lines
        lines = (
            lines[:head]
            + [f"... ({total - head - tail} lines omitted)"]
            + lines[total - tail :]
        )
    elif fallback_filter.head_lines is not None and total > fallback_filter.head_lines:
        kept = fallback_filter.head_lines
        lines = lines[:kept] + [f"... ({total - kept} lines omitted)"]
    elif fallback_filter.tail_lines is not None and total > fallback_filter.tail_lines:
        omitted = total - fallback_filter.tail_lines
        lines = [f"... ({omitted} lines omitted)"] + lines[omitted:]

    if fallback_filter.max_lines is not None and len(lines) > fallback_filter.max_lines:
        truncated = len(lines) - fallback_filter.max_lines
        lines = lines[: fallback_filter.max_lines] + [
            f"... ({truncated} lines truncated)"
        ]

    result = "\n".join(lines)
    if result.strip() or fallback_filter.on_empty is None:
        return result
    return fallback_filter.on_empty


def apply_builtin_fallback(command: str, text: str) -> tuple[str, str] | None:
    if os.getenv("RTK_NO_TOML") == "1":
        return None

    fallback_filter = find_fallback_filter(command)
    if os.getenv("RTK_TOML_DEBUG"):
        status = fallback_filter.name if fallback_filter is not None else "none"
        print(f"[pytk:toml] matched filter: {status}", file=sys.stderr)
    if fallback_filter is None:
        return None
    return f"toml.{fallback_filter.name}", apply_fallback_filter(fallback_filter, text)
