from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

from .models import Rule


@lru_cache(maxsize=1)
def load_rules() -> tuple[Rule, ...]:
    data = json.loads(
        resources.files("pytk_ai.data").joinpath("rules.json").read_text(encoding="utf-8")
    )
    return tuple(
        Rule(
            pattern=item["pattern"],
            pytk_ai_cmd=item["pytk_ai_cmd"],
            rewrite_prefixes=tuple(
                sorted(item["rewrite_prefixes"], key=len, reverse=True)
            ),
            category=item["category"],
            savings_pct=float(item["savings_pct"]),
        )
        for item in data
    )


def match_rule(command: str, rules: tuple[Rule, ...] | None = None) -> Rule | None:
    for rule in rules or load_rules():
        if re.search(rule.pattern, command):
            return rule
    return None


def rule_filter_hint(rule: Rule) -> str | None:
    if not rule.pytk_ai_cmd:
        return None
    parts = rule.pytk_ai_cmd.split()
    if len(parts) >= 2 and parts[0] == "pytk-ai":
        return parts[1]
    return parts[-1]
