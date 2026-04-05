from __future__ import annotations

import os
import re

_ENV_PREFIX_RE = re.compile(
    r"^(?:sudo\s+|env\s+|[A-Z_][A-Z0-9_]*=(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|[^\s]*)\s+)+"
)
_HEAD_N_RE = re.compile(r"^head\s+-(\d+)\s+(.+)$")
_HEAD_LINES_RE = re.compile(r"^head\s+--lines=(\d+)\s+(.+)$")
_TAIL_N_RE = re.compile(r"^tail\s+-(\d+)\s+(.+)$")
_TAIL_N_SPACE_RE = re.compile(r"^tail\s+-n\s+(\d+)\s+(.+)$")
_TAIL_LINES_EQ_RE = re.compile(r"^tail\s+--lines=(\d+)\s+(.+)$")
_TAIL_LINES_SPACE_RE = re.compile(r"^tail\s+--lines\s+(\d+)\s+(.+)$")


def has_disabled_prefix(command: str) -> bool:
    return bool(re.search(r"(?:^|\s)(?:PYTK_AI|RTK)_DISABLED=1(?:\s|$)", command))


def strip_env_prefix(command: str) -> tuple[str, str]:
    match = _ENV_PREFIX_RE.match(command)
    if not match:
        return "", command.strip()
    prefix = match.group(0)
    return prefix, command[len(prefix) :].strip()


def normalize_absolute_first_token(command: str) -> str:
    parts = command.split(maxsplit=1)
    if not parts:
        return command
    first = parts[0]
    if "/" not in first:
        return command
    rebuilt = os.path.basename(first)
    if len(parts) > 1:
        rebuilt += f" {parts[1]}"
    return rebuilt


def strip_trailing_redirect_suffix(command: str) -> tuple[str, str]:
    parts = command.split()
    if not parts:
        return command, ""

    idx = len(parts)
    while idx > 0:
        token = parts[idx - 1]
        if re.match(r"^(?:\d+)?(?:>>?|<|&>).*$", token):
            idx -= 1
            continue
        if idx > 1 and re.match(r"^(?:\d+)?(?:>>?|<|&>)$", parts[idx - 2]):
            idx -= 2
            continue
        break

    if idx == len(parts):
        return command, ""

    command_part = " ".join(parts[:idx])
    suffix = " ".join(parts[idx:])
    return command_part, f" {suffix}" if suffix else ""


def strip_word_prefix(command: str, prefix: str) -> str | None:
    if command == prefix:
        return ""
    if (
        command.startswith(prefix)
        and len(command) > len(prefix)
        and command[len(prefix)] == " "
    ):
        return command[len(prefix) + 1 :].lstrip()
    return None


def rewrite_line_range(command: str, redirect_suffix: str = "") -> str | None:
    for regex in (_HEAD_N_RE, _HEAD_LINES_RE):
        match = regex.match(command)
        if match:
            count, path = match.group(1), match.group(2)
            return f"pytk-ai read {path} --max-lines {count}{redirect_suffix}"
    if command.startswith("head -"):
        return None
    for regex in (
        _TAIL_N_RE,
        _TAIL_N_SPACE_RE,
        _TAIL_LINES_EQ_RE,
        _TAIL_LINES_SPACE_RE,
    ):
        match = regex.match(command)
        if match:
            count, path = match.group(1), match.group(2)
            return f"pytk-ai read {path} --tail-lines {count}{redirect_suffix}"
    return None


def infer_filter_hint(command: str) -> str | None:
    _, command = strip_env_prefix(command.strip())
    normalized = normalize_absolute_first_token(command)
    if not normalized:
        return None
    if normalized.startswith("pytk-ai read"):
        return "read"
    if normalized.startswith("pytk-ai "):
        parts = normalized.split(maxsplit=2)
        return parts[1] if len(parts) > 1 else "pytk-ai"
    if normalized.startswith(("cat ", "head ", "tail ")):
        return "read"
    if normalized.startswith(("rg ", "grep ")):
        return "grep"
    if normalized.startswith("tree") and (normalized == "tree" or normalized[4] == " "):
        return "tree"
    if normalized.startswith("wc") and (normalized == "wc" or normalized[2] == " "):
        return "wc"
    if normalized.startswith("diff ") or normalized == "diff":
        return "diff"
    if normalized.startswith(("pip list", "pip outdated", "uv sync", "bundle install")):
        return "package"
    if normalized.startswith("uv pip list"):
        return "package"
    if re.match(r"^(?:npm|pnpm)\s+(?:list|ls)(?:\s|$)", normalized):
        return "package"
    if re.match(r"^(?:npx\s+|pnpm\s+)?prisma\s+generate(?:\s|$)", normalized):
        return "package"
    if re.match(r"^cargo\s+(build|clippy|check|fmt)(\s|$)", normalized):
        return "cargo"
    if normalized.startswith("cargo test"):
        return "test"
    if re.match(r"^(?:npm|pnpm|yarn|make)\s+test(?:\s|$)", normalized):
        return "test"
    if normalized.startswith("git "):
        return "git"
    if re.match(r"^gh\s+pr\s+(?:list|view)(?:\s|$)", normalized):
        return "gh"
    if re.match(r"^gh\s+issue\s+list(?:\s|$)", normalized):
        return "gh"
    if re.match(r"^gh\s+run\s+list(?:\s|$)", normalized):
        return "gh"
    if normalized.startswith("gh "):
        return None
    if re.match(r"^(?:npx\s+|pnpm\s+)?tsc(\s|$)", normalized):
        return "tsc"
    if re.match(r"^(?:npx\s+|pnpm\s+)?next\s+build(\s|$)", normalized):
        return "next"
    if re.match(r"^(?:npx\s+|pnpm\s+)?(?:eslint|biome|lint)(\s|$)", normalized):
        return "lint"
    if (
        normalized.startswith("python -m pytest")
        or normalized.startswith("pytest ")
        or normalized == "pytest"
    ):
        return "pytest"
    if (
        normalized.startswith("python -m mypy")
        or normalized.startswith("mypy ")
        or normalized == "mypy"
    ):
        return "mypy"
    if normalized.startswith("ruff "):
        return "ruff"
    if re.match(r"^go\s+(test|build|vet)(\s|$)", normalized):
        return "go"
    if normalized.startswith("go "):
        return None
    if normalized.startswith("golangci-lint"):
        return "golangci-lint"
    if re.match(r"^(?:bundle\s+exec\s+)?rspec(\s|$)", normalized):
        return "rspec"
    if re.match(r"^(?:bundle\s+exec\s+)?rubocop(\s|$)", normalized):
        return "rubocop"
    if re.match(r"^docker\s+(?:ps|images|logs)(?:\s|$)", normalized):
        return "docker"
    if re.match(r"^docker\s+compose\s+ps(?:\s|$)", normalized):
        return "docker"
    if normalized.startswith("docker "):
        return None
    if re.match(r"^kubectl\s+(?:pods|services|logs)(?:\s|$)", normalized):
        return "kubectl"
    if re.match(r"^kubectl\s+get\s+(?:pods|services)(?:\s|$)", normalized):
        return "kubectl"
    if normalized.startswith("kubectl "):
        return None
    if re.match(
        r"^aws\s+\S+\s+(?:describe|get|list)(?:-[a-z0-9-]+)?(?:\s|$)",
        normalized,
    ) or re.match(r"^aws\s+(?:sts\s+get-caller-identity|s3\s+ls)(?:\s|$)", normalized):
        return "aws"
    if normalized.startswith("aws "):
        return None
    if re.match(r"^terraform\s+(?:plan|validate)(?:\s|$)", normalized):
        return "terraform"
    if normalized.startswith("terraform "):
        return None
    if normalized.startswith("curl ") or normalized == "curl":
        return "curl"
    if normalized.startswith("wget ") or normalized == "wget":
        return "wget"
    if normalized.startswith("ls"):
        return "ls"
    if normalized.startswith("find ") or normalized == "find":
        return "find"
    return normalized.split(maxsplit=1)[0]
