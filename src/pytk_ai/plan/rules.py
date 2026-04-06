from __future__ import annotations

import re
from functools import lru_cache

from .models import Rule


def _rule(
    pattern: str,
    pytk_ai_cmd: str,
    rewrite_prefixes: tuple[str, ...],
    category: str,
    savings_pct: float,
) -> Rule:
    return Rule(
        pattern=pattern,
        pytk_ai_cmd=pytk_ai_cmd,
        rewrite_prefixes=tuple(sorted(rewrite_prefixes, key=len, reverse=True)),
        category=category,
        savings_pct=float(savings_pct),
    )


_RULES: tuple[Rule, ...] = (
    _rule(
        r"^(?:uv\s+pip\s+list(?:\s+.*--outdated|\s+--outdated.*)?|pip\s+(?:list(?:\s+.*--outdated|\s+--outdated.*)?|outdated))(\s|$)",
        "pytk-ai package",
        ("uv pip list", "pip list", "pip outdated"),
        "PackageManager",
        78.0,
    ),
    _rule(r"^uv\s+sync(\s|$)", "pytk-ai package", ("uv sync",), "PackageManager", 80.0),
    _rule(
        r"^uv\s+pip\s+install(\s|$)",
        "pytk-ai package",
        ("uv pip install",),
        "PackageManager",
        75.0,
    ),
    _rule(
        r"^pnpm\s+(list|ls|outdated|install)(\s|$)",
        "pytk-ai package",
        ("pnpm outdated", "pnpm install", "pnpm list", "pnpm ls"),
        "PackageManager",
        75.0,
    ),
    _rule(
        r"^npm\s+(list|ls|run|exec)(\s|$)",
        "pytk-ai package",
        ("npm run", "npm exec", "npm list", "npm ls"),
        "PackageManager",
        75.0,
    ),
    _rule(
        r"^bundle\s+(install|update)(\s|$)",
        "pytk-ai package",
        ("bundle update", "bundle install"),
        "PackageManager",
        85.0,
    ),
    _rule(
        r"^(npx\s+|pnpm\s+)?prisma\s+(generate|migrate\s+(dev|status|deploy)|db\s+push)(\s|$)",
        "pytk-ai package",
        (
            "pnpm prisma db push",
            "npx prisma db push",
            "prisma db push",
            "pnpm prisma migrate deploy",
            "npx prisma migrate deploy",
            "prisma migrate deploy",
            "pnpm prisma migrate status",
            "npx prisma migrate status",
            "prisma migrate status",
            "pnpm prisma migrate dev",
            "npx prisma migrate dev",
            "prisma migrate dev",
            "pnpm prisma generate",
            "npx prisma generate",
            "prisma generate",
        ),
        "PackageManager",
        80.0,
    ),
    _rule(
        r"^git\s+(?:-[Cc]\s+\S+\s+)*(status|log|diff|show|add|commit|push|pull|branch|fetch|stash|worktree)",
        "pytk-ai git",
        ("git",),
        "Git",
        70.0,
    ),
    _rule(r"^gh\s+", "pytk-ai gh", ("gh",), "GitHub", 82.0),
    _rule(r"^gt\s+", "pytk-ai gt", ("gt",), "Git", 75.0),
    _rule(r"^cargo\s+test(\s|$)", "pytk-ai test", ("cargo test",), "Tests", 90.0),
    _rule(
        r"^cargo\s+(build|clippy|check|fmt|install|nextest)",
        "pytk-ai cargo",
        ("cargo",),
        "Cargo",
        80.0,
    ),
    _rule(
        r"^(npm|pnpm|yarn|make)\s+test(\s|$)",
        "pytk-ai test",
        ("pnpm test", "npm test", "yarn test", "make test"),
        "Tests",
        90.0,
    ),
    _rule(r"^npx\s+", "pytk-ai npx", ("npx",), "PackageManager", 70.0),
    _rule(
        r"^(cat|head|tail)\s+", "pytk-ai read", ("cat", "head", "tail"), "Files", 60.0
    ),
    _rule(r"^(rg|grep)\s+", "pytk-ai grep", ("rg", "grep"), "Files", 75.0),
    _rule(r"^ls(\s|$)", "pytk-ai ls", ("ls",), "Files", 65.0),
    _rule(r"^find\s+", "pytk-ai find", ("find",), "Files", 70.0),
    _rule(
        r"^(npx\s+|pnpm\s+)?tsc(\s|$)",
        "pytk-ai tsc",
        ("pnpm tsc", "npx tsc", "tsc"),
        "Build",
        83.0,
    ),
    _rule(
        r"^(?:npx\s+|pnpm(?:\s+exec)?\s+|npm\s+exec\s+|yarn\s+|bunx\s+)?prettier(\s|$)",
        "pytk-ai format",
        (
            "pnpm exec prettier",
            "npm exec prettier",
            "pnpm prettier",
            "npx prettier",
            "yarn prettier",
            "bunx prettier",
            "prettier",
        ),
        "Build",
        70.0,
    ),
    _rule(
        r"^(?:npx\s+|pnpm(?:\s+exec)?\s+|npm\s+exec\s+|yarn\s+|bunx\s+)?biome\s+format(\s|$)",
        "pytk-ai format",
        (
            "pnpm exec biome format",
            "npm exec biome format",
            "pnpm biome format",
            "npx biome format",
            "yarn biome format",
            "bunx biome format",
            "biome format",
        ),
        "Build",
        70.0,
    ),
    _rule(
        r"^(?:npx\s+|pnpm(?:\s+exec)?\s+|npm\s+exec\s+|yarn\s+|bunx\s+)?biome\s+check(?:\s+.*)?(?:--write|--fix|--unsafe|--apply|--apply-unsafe)(?:\s|$)",
        "pytk-ai format",
        (
            "pnpm exec biome check",
            "npm exec biome check",
            "pnpm biome check",
            "npx biome check",
            "yarn biome check",
            "bunx biome check",
            "biome check",
        ),
        "Build",
        70.0,
    ),
    _rule(
        r"^(?:npx\s+|pnpm(?:\s+exec)?\s+|npm\s+exec\s+|yarn\s+|bunx\s+)?(?:eslint|biome|lint)(\s|$)",
        "pytk-ai lint",
        (
            "pnpm exec eslint",
            "pnpm exec biome",
            "npm exec eslint",
            "npm exec biome",
            "pnpm lint",
            "yarn eslint",
            "yarn biome",
            "bunx eslint",
            "bunx biome",
            "npx eslint",
            "npx biome",
            "eslint",
            "biome",
            "lint",
        ),
        "Build",
        84.0,
    ),
    _rule(r"^black(\s|$)", "pytk-ai format", ("black",), "Build", 70.0),
    _rule(
        r"^(npx\s+|pnpm\s+)?next\s+build",
        "pytk-ai next",
        ("npx next build", "pnpm next build", "next build"),
        "Build",
        87.0,
    ),
    _rule(
        r"^(pnpm\s+|npx\s+)?(vitest|jest|test)(\s|$)",
        "pytk-ai vitest",
        ("pnpm vitest", "npx vitest", "vitest", "jest"),
        "Tests",
        99.0,
    ),
    _rule(
        r"^(npx\s+|pnpm\s+)?playwright",
        "pytk-ai playwright",
        ("npx playwright", "pnpm playwright", "playwright"),
        "Tests",
        94.0,
    ),
    _rule(
        r"^docker\s+(ps|images|logs|compose\s+(?:ps|logs|build))(\s|$)",
        "pytk-ai docker",
        ("docker",),
        "Infra",
        85.0,
    ),
    _rule(
        r"^kubectl\s+((get\s+)?(pods|services)|logs)(\s|$)",
        "pytk-ai kubectl",
        ("kubectl",),
        "Infra",
        85.0,
    ),
    _rule(
        r"^aws\s+\S+\s+((describe|get|list)(-[a-z0-9-]+)?|sts\s+get-caller-identity|s3\s+ls)(\s|$)",
        "pytk-ai aws",
        ("aws",),
        "Infra",
        80.0,
    ),
    _rule(r"^tree(\s|$)", "pytk-ai tree", ("tree",), "Files", 70.0),
    _rule(r"^wc(\s|$)", "pytk-ai wc", ("wc",), "Files", 55.0),
    _rule(r"^diff(\s|$)", "pytk-ai diff", ("diff",), "Files", 60.0),
    _rule(r"^curl\s+", "pytk-ai curl", ("curl",), "Network", 70.0),
    _rule(r"^wget\s+", "pytk-ai wget", ("wget",), "Network", 65.0),
    _rule(
        r"^(python3?\s+-m\s+)?mypy(\s|$)",
        "pytk-ai mypy",
        ("python3 -m mypy", "python -m mypy", "mypy"),
        "Build",
        80.0,
    ),
    _rule(r"^ruff\s+(check|format)", "pytk-ai ruff", ("ruff",), "Python", 80.0),
    _rule(
        r"^(python\s+-m\s+)?pytest(\s|$)",
        "pytk-ai pytest",
        ("python -m pytest", "pytest"),
        "Python",
        90.0,
    ),
    _rule(
        r"^(pip3?|uv\s+pip)\s+(list|outdated|install)",
        "pytk-ai pip",
        ("pip3", "pip", "uv pip"),
        "Python",
        75.0,
    ),
    _rule(r"^go\s+(test|build|vet)", "pytk-ai go", ("go",), "Go", 85.0),
    _rule(
        r"^golangci-lint(\s|$)",
        "pytk-ai golangci-lint",
        ("golangci-lint", "golangci"),
        "Go",
        85.0,
    ),
    _rule(
        r"^(?:bundle\s+exec\s+)?(?:bin/)?(?:rake|rails)\s+test",
        "pytk-ai rake",
        ("bundle exec rails", "bundle exec rake", "bin/rails", "rails", "rake"),
        "Ruby",
        85.0,
    ),
    _rule(
        r"^(?:bundle\s+exec\s+)?rspec(?:\s|$)",
        "pytk-ai rspec",
        ("bundle exec rspec", "bin/rspec", "rspec"),
        "Tests",
        65.0,
    ),
    _rule(
        r"^(?:bundle\s+exec\s+)?rubocop(?:\s|$)",
        "pytk-ai rubocop",
        ("bundle exec rubocop", "rubocop"),
        "Build",
        65.0,
    ),
    _rule(r"^psql(\s|$)", "pytk-ai psql", ("psql",), "Infra", 75.0),
    _rule(
        r"^ansible-playbook\b",
        "pytk-ai ansible-playbook",
        ("ansible-playbook",),
        "Infra",
        70.0,
    ),
    _rule(
        r"^brew\s+(install|upgrade)\b",
        "pytk-ai brew",
        ("brew",),
        "PackageManager",
        65.0,
    ),
    _rule(
        r"^composer\s+(install|update|require)\b",
        "pytk-ai composer",
        ("composer",),
        "PackageManager",
        65.0,
    ),
    _rule(r"^df(\s|$)", "pytk-ai df", ("df",), "System", 60.0),
    _rule(
        r"^dotnet\s+(build|test|restore|format)\b",
        "pytk-ai dotnet",
        ("dotnet",),
        "Build",
        70.0,
    ),
    _rule(r"^du\b", "pytk-ai du", ("du",), "System", 60.0),
    _rule(
        r"^fail2ban-client\b",
        "pytk-ai fail2ban-client",
        ("fail2ban-client",),
        "Infra",
        60.0,
    ),
    _rule(r"^gcloud\b", "pytk-ai gcloud", ("gcloud",), "Infra", 65.0),
    _rule(r"^hadolint\b", "pytk-ai hadolint", ("hadolint",), "Build", 65.0),
    _rule(r"^helm\b", "pytk-ai helm", ("helm",), "Infra", 65.0),
    _rule(r"^iptables\b", "pytk-ai iptables", ("iptables",), "Infra", 60.0),
    _rule(r"^make\b", "pytk-ai make", ("make",), "Build", 65.0),
    _rule(r"^markdownlint\b", "pytk-ai markdownlint", ("markdownlint",), "Build", 65.0),
    _rule(r"^mix\s+(compile|format)(\s|$)", "pytk-ai mix", ("mix",), "Build", 65.0),
    _rule(
        r"^mvn\s+(compile|package|clean|install)\b",
        "pytk-ai mvn",
        ("mvn",),
        "Build",
        70.0,
    ),
    _rule(r"^ping\b", "pytk-ai ping", ("ping",), "Network", 60.0),
    _rule(r"^pio\s+run", "pytk-ai pio", ("pio",), "Build", 65.0),
    _rule(
        r"^poetry\s+(install|lock|update)\b",
        "pytk-ai poetry",
        ("poetry",),
        "Python",
        65.0,
    ),
    _rule(r"^pre-commit\b", "pytk-ai pre-commit", ("pre-commit",), "Build", 65.0),
    _rule(r"^ps(\s|$)", "pytk-ai ps", ("ps",), "System", 60.0),
    _rule(r"^quarto\s+render", "pytk-ai quarto", ("quarto",), "Build", 65.0),
    _rule(r"^rsync\b", "pytk-ai rsync", ("rsync",), "Network", 65.0),
    _rule(r"^shellcheck\b", "pytk-ai shellcheck", ("shellcheck",), "Build", 65.0),
    _rule(
        r"^shopify\s+theme\s+(push|pull)",
        "pytk-ai shopify",
        ("shopify",),
        "Build",
        65.0,
    ),
    _rule(r"^sops\b", "pytk-ai sops", ("sops",), "Infra", 60.0),
    _rule(r"^swift\s+(build|test)\b", "pytk-ai swift", ("swift",), "Build", 65.0),
    _rule(
        r"^systemctl\s+status\b", "pytk-ai systemctl", ("systemctl",), "System", 65.0
    ),
    _rule(
        r"^terraform\s+(plan|validate)(\s|$)",
        "pytk-ai terraform",
        ("terraform",),
        "Infra",
        70.0,
    ),
    _rule(
        r"^tofu\s+(fmt|init|plan|validate)(\s|$)",
        "pytk-ai tofu",
        ("tofu",),
        "Infra",
        70.0,
    ),
    _rule(r"^trunk\s+build", "pytk-ai trunk", ("trunk",), "Build", 65.0),
    _rule(r"^yamllint\b", "pytk-ai yamllint", ("yamllint",), "Build", 65.0),
)


@lru_cache(maxsize=1)
def load_rules() -> tuple[Rule, ...]:
    return _RULES


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
