from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from importlib import resources
from typing import Sequence


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    ptk_cmd: str
    rewrite_prefixes: tuple[str, ...]
    category: str
    savings_pct: float


@dataclass(frozen=True)
class RewriteResult:
    output: str
    matched: bool
    changed: bool


_ENV_PREFIX_RE = re.compile(
    r"^(?:sudo\s+|env\s+|[A-Z_][A-Z0-9_]*=(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|[^\s]*)\s+)+"
)
_HEAD_N_RE = re.compile(r"^head\s+-(\d+)\s+(.+)$")
_HEAD_LINES_RE = re.compile(r"^head\s+--lines=(\d+)\s+(.+)$")
_TAIL_N_RE = re.compile(r"^tail\s+-(\d+)\s+(.+)$")
_TAIL_N_SPACE_RE = re.compile(r"^tail\s+-n\s+(\d+)\s+(.+)$")
_TAIL_LINES_EQ_RE = re.compile(r"^tail\s+--lines=(\d+)\s+(.+)$")
_TAIL_LINES_SPACE_RE = re.compile(r"^tail\s+--lines\s+(\d+)\s+(.+)$")

_RULES_DATA = json.loads(
    resources.files("ptk.data").joinpath("rules.json").read_text(encoding="utf-8")
)

RULES: tuple[Rule, ...] = tuple(
    Rule(
        pattern=re.compile(item["pattern"]),
        ptk_cmd=item["ptk_cmd"],
        rewrite_prefixes=tuple(sorted(item["rewrite_prefixes"], key=len, reverse=True)),
        category=item["category"],
        savings_pct=float(item["savings_pct"]),
    )
    for item in _RULES_DATA
)


def _has_disabled_prefix(cmd: str) -> bool:
    return bool(re.search(r"(?:^|\s)(?:PTK|RTK)_DISABLED=1(?:\s|$)", cmd))


def _strip_env_prefix(cmd: str) -> tuple[str, str]:
    match = _ENV_PREFIX_RE.match(cmd)
    if not match:
        return "", cmd.strip()
    prefix = match.group(0)
    return prefix, cmd[len(prefix) :].strip()


def _normalize_absolute_first_token(cmd: str) -> str:
    parts = cmd.split(maxsplit=1)
    if not parts:
        return cmd
    first = parts[0]
    if "/" not in first:
        return cmd
    rebuilt = os.path.basename(first)
    if len(parts) > 1:
        rebuilt += f" {parts[1]}"
    return rebuilt


def _strip_trailing_redirect_suffix(cmd: str) -> tuple[str, str]:
    # Lightweight suffix stripper for common trailing redirect tokens.
    parts = cmd.split()
    if not parts:
        return cmd, ""

    idx = len(parts)
    while idx > 0:
        tok = parts[idx - 1]
        if re.match(r"^(?:\d+)?(?:>>?|<|&>).*$", tok):
            idx -= 1
            continue
        if idx > 1 and re.match(r"^(?:\d+)?(?:>>?|<|&>)$", tok):
            idx -= 2
            continue
        break

    if idx == len(parts):
        return cmd, ""

    cmd_part = " ".join(parts[:idx])
    suffix = " ".join(parts[idx:])
    return cmd_part, (f" {suffix}" if suffix else "")


def _match_rule(cmd: str) -> Rule | None:
    for rule in RULES:
        if rule.pattern.search(cmd):
            return rule
    return None


def _strip_word_prefix(cmd: str, prefix: str) -> str | None:
    if cmd == prefix:
        return ""
    if cmd.startswith(prefix) and len(cmd) > len(prefix) and cmd[len(prefix)] == " ":
        return cmd[len(prefix) + 1 :].lstrip()
    return None


def _rewrite_line_range(cmd: str, redirect_suffix: str) -> str | None:
    for regex in (_HEAD_N_RE, _HEAD_LINES_RE):
        match = regex.match(cmd)
        if match:
            n, file = match.group(1), match.group(2)
            return f"ptk read {file} --max-lines {n}{redirect_suffix}"
    if cmd.startswith("head -"):
        return None
    for regex in (
        _TAIL_N_RE,
        _TAIL_N_SPACE_RE,
        _TAIL_LINES_EQ_RE,
        _TAIL_LINES_SPACE_RE,
    ):
        match = regex.match(cmd)
        if match:
            n, file = match.group(1), match.group(2)
            return f"ptk read {file} --tail-lines {n}{redirect_suffix}"
    return None


def _rewrite_segment(
    segment: str, excluded: Sequence[str] = ()
) -> RewriteResult | None:
    trimmed = segment.strip()
    if not trimmed:
        return None

    cmd_part, redirect_suffix = _strip_trailing_redirect_suffix(trimmed)

    if cmd_part.startswith("ptk ") or cmd_part == "ptk":
        return RewriteResult(output=trimmed, matched=True, changed=False)

    if cmd_part.startswith("head -") or cmd_part.startswith("tail "):
        rewritten = _rewrite_line_range(cmd_part, redirect_suffix)
        if rewritten is not None:
            return RewriteResult(
                output=rewritten, matched=True, changed=(rewritten != trimmed)
            )
        return None

    if cmd_part.startswith("cat "):
        args = cmd_part[len("cat ") :].lstrip()
        if args.startswith("-") and not (args.startswith("-n ") or args == "-n"):
            return None

    prefix, cmd_clean = _strip_env_prefix(cmd_part)
    if _has_disabled_prefix(prefix + cmd_clean):
        return None

    cmd_match = _normalize_absolute_first_token(cmd_clean)
    rule = _match_rule(cmd_match)
    if rule is None:
        return None

    base = cmd_match.split(maxsplit=1)[0] if cmd_match else ""
    if base and base in excluded:
        return None

    if rule.ptk_cmd == "ptk gh":
        lowered = cmd_match.lower()
        if any(flag in lowered for flag in ("--json", "--jq", "--template")):
            return None

    for rewrite_prefix in rule.rewrite_prefixes:
        rest = _strip_word_prefix(cmd_match, rewrite_prefix)
        if rest is None:
            continue
        rewritten = f"{prefix}{rule.ptk_cmd}"
        if rest:
            rewritten += f" {rest}"
        rewritten += redirect_suffix
        return RewriteResult(
            output=rewritten, matched=True, changed=(rewritten != trimmed)
        )

    return None


def _scan_compound(cmd: str) -> tuple[list[tuple[str, str | None]], str | None]:
    segments: list[tuple[str, str | None]] = []
    start = 0
    quote: str | None = None
    escape = False
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\" and quote != "'":
            escape = True
            i += 1
            continue
        if quote is not None:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            i += 1
            continue

        if cmd.startswith("&&", i):
            segments.append((cmd[start:i].strip(), "&&"))
            i += 2
            start = i
            continue
        if cmd.startswith("||", i):
            segments.append((cmd[start:i].strip(), "||"))
            i += 2
            start = i
            continue
        if ch == ";":
            segments.append((cmd[start:i].strip(), ";"))
            i += 1
            start = i
            continue
        if ch == "|":
            segments.append((cmd[start:i].strip(), "|"))
            return segments, cmd[i + 1 :].lstrip()
        if ch == "&" and not cmd.startswith("&>", i) and (i == 0 or cmd[i - 1] != ">"):
            if not cmd.startswith("&&", i):
                segments.append((cmd[start:i].strip(), "&"))
                i += 1
                start = i
                continue
        i += 1

    segments.append((cmd[start:].strip(), None))
    return segments, None


def rewrite_command(
    cmd: str, excluded: Sequence[str] | None = None
) -> RewriteResult | None:
    excluded = tuple(excluded or ())
    trimmed = cmd.strip()
    if not trimmed:
        return None

    if "<<" in trimmed or "$((" in trimmed:
        return None

    has_compound = any(op in trimmed for op in ("&&", "||", ";", "|", " & "))
    if not has_compound and (trimmed.startswith("ptk ") or trimmed == "ptk"):
        return RewriteResult(output=trimmed, matched=True, changed=False)

    segments, pipe_remainder = _scan_compound(trimmed)
    if pipe_remainder is not None:
        left, op = segments[-1]
        if left.startswith(("find ", "fd ")) or left in {"find", "fd"}:
            return None
        rewritten = _rewrite_segment(left, excluded)
        if rewritten is None:
            return None
        if op != "|":
            return None
        output = f"{rewritten.output} | {pipe_remainder}"
        changed = rewritten.changed or output != trimmed
        return RewriteResult(output=output, matched=True, changed=changed)

    any_changed = False
    parts: list[str] = []
    for segment, op in segments:
        rewritten = _rewrite_segment(segment, excluded)
        if rewritten is None:
            parts.append(segment)
        else:
            parts.append(rewritten.output)
            any_changed = any_changed or rewritten.changed
        if op is not None:
            parts.append(f" {op} ")

    output = "".join(parts).strip()
    if output == trimmed and not any_changed:
        return None
    return RewriteResult(output=output, matched=True, changed=(output != trimmed))


def rewrite_exit_code(
    cmd: str, excluded: Sequence[str] | None = None
) -> tuple[int, str | None]:
    result = rewrite_command(cmd, excluded=excluded)
    if result is None:
        return 1, None
    return 0, result.output


def load_rules() -> tuple[Rule, ...]:
    return RULES


def summarize_rewrite(result: RewriteResult | None) -> str:
    if result is None:
        return ""
    return result.output
