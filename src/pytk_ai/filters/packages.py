from __future__ import annotations

import json
import re

from ..models import FilterResult
from ..plan.normalize import normalize_absolute_first_token, strip_env_prefix
from .base import make_filter_result, strip_ansi
from .generic import _combine_streams, filter_generic_output

_BLOCK_ART_CHARS = ("█", "▀", "▄", "┌", "└", "│")
_TABLE_RULE_RE = re.compile(r"^-{3,}(?:\s+-{3,})+$")
_VERSIONED_PACKAGE_RE = re.compile(r"(?P<name>@?[^@\s][^@\s]*?)@(?P<version>[^\s]+)$")
_PRISMA_COUNT_RE = re.compile(r"(?P<count>\d+)\s+(?P<kind>models?|enums?|types?)\b")


def _normalized_command(command: str) -> str:
    _, stripped = strip_env_prefix(command.strip())
    return normalize_absolute_first_token(stripped)


def _command_kind(command: str) -> tuple[str, str] | None:
    normalized = _normalized_command(command)
    parts = normalized.split()
    if not parts:
        return None

    if parts[:2] == ["pytk-ai", "package"]:
        parts = parts[2:]
    if not parts:
        return None

    if parts[:2] == ["uv", "sync"]:
        return "uv", "sync"
    if parts[:2] == ["bundle", "install"]:
        return "bundle", "install"
    if parts[:2] == ["bundle", "update"]:
        return "bundle", "update"
    if parts[:2] == ["pip", "outdated"]:
        return "pip", "outdated"
    if parts[:2] == ["pip", "list"]:
        return ("pip", "outdated") if "--outdated" in parts[2:] else ("pip", "list")
    if parts[:3] == ["uv", "pip", "list"]:
        return ("pip", "outdated") if "--outdated" in parts[3:] else ("pip", "list")
    if parts[:2] in (["npm", "list"], ["npm", "ls"]):
        return "npm", "list"
    if parts[:2] in (["pnpm", "list"], ["pnpm", "ls"]):
        return "pnpm", "list"
    if parts[:2] == ["prisma", "generate"]:
        return "prisma", "generate"
    if parts[:3] in (["npx", "prisma", "generate"], ["pnpm", "prisma", "generate"]):
        return "prisma", "generate"
    return None


def _filter_name(kind: str, subkind: str) -> str:
    return f"{kind}.{subkind}"


def _append_warnings(lines: list[str], stderr: str) -> None:
    warnings = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in warnings[:5]:
        lines.append(line)
    if len(warnings) > 5:
        lines.append(f"... +{len(warnings) - 5} more warning lines")


def _parse_package_table(text: str) -> list[tuple[str, str]]:
    packages: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("Package ")
            or line.startswith("package ")
            or _TABLE_RULE_RE.match(line)
        ):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        packages.append((parts[0], parts[1]))
    return packages


def _parse_pip_list(stdout: str) -> list[tuple[str, str]] | None:
    stripped = stdout.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        return sorted(
            (item["name"], item["version"])
            for item in payload
            if item.get("name") and item.get("version")
        )
    if (
        "==" in stripped
        and "\n" in stripped
        or re.search(r"^[A-Za-z0-9_.-]+==", stripped)
    ):
        return None
    packages = _parse_package_table(stripped)
    return sorted(packages) if packages else None


def _parse_pip_outdated(stdout: str) -> list[tuple[str, str, str]] | None:
    stripped = stdout.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        packages = []
        for item in payload:
            name = item.get("name")
            current = item.get("version") or item.get("current_version")
            latest = item.get("latest_version") or item.get("latest")
            if name and current and latest:
                packages.append((name, current, latest))
        return sorted(packages)

    packages: list[tuple[str, str, str]] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Package ") or _TABLE_RULE_RE.match(line):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        packages.append((parts[0], parts[1], parts[2]))
    return sorted(packages)


def _summarize_pip_list(stdout: str, stderr: str) -> str | None:
    packages = _parse_pip_list(stdout)
    if packages is None:
        return None
    if not packages:
        return "pip list: No packages installed"
    lines = [f"pip list: {len(packages)} packages"]
    for name, version in packages[:12]:
        lines.append(f"  {name} ({version})")
    if len(packages) > 12:
        lines.append(f"... +{len(packages) - 12} more packages")
    _append_warnings(lines, stderr)
    return "\n".join(lines)


def _summarize_pip_outdated(stdout: str, stderr: str) -> str | None:
    packages = _parse_pip_outdated(stdout)
    if packages is None:
        return None
    if not packages:
        return "pip outdated: All packages up to date"
    lines = [f"pip outdated: {len(packages)} packages"]
    for name, current, latest in packages[:15]:
        lines.append(f"  {name}: {current} -> {latest}")
    if len(packages) > 15:
        lines.append(f"... +{len(packages) - 15} more packages")
    _append_warnings(lines, stderr)
    return "\n".join(lines)


def _summarize_uv_sync(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.rstrip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "uv sync: ok"

    package_changes = [
        line.strip() for line in lines if line.lstrip().startswith(("+ ", "- ", "~ "))
    ]
    summaries = [
        line.strip()
        for line in lines
        if line.strip().startswith(
            ("Installed ", "Uninstalled ", "Updated ", "Added ", "Removed ")
        )
    ]
    warnings = [
        line.strip()
        for line in lines
        if line.strip().lower().startswith(("warning:", "warn["))
    ]

    if (
        any("Audited " in line for line in lines)
        and not package_changes
        and not summaries
    ):
        summary = "uv sync: ok (up to date)"
        if warnings:
            return "\n".join([summary, *warnings[:5]])
        return summary

    output = summaries[:3] or ["uv sync: ok"]
    output.extend(package_changes[:12])
    if len(package_changes) > 12:
        output.append(f"... +{len(package_changes) - 12} more packages")
    output.extend(warnings[:5])
    return "\n".join(output)


def _extract_dependency_entries_from_json(payload: object) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        dependencies = node.get("dependencies")
        if isinstance(dependencies, dict):
            for name, dep in dependencies.items():
                version = ""
                if isinstance(dep, dict):
                    version = str(dep.get("version") or "")
                entries.append((name, version))
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    walk(payload)
    deduped: dict[str, str] = {}
    for name, version in entries:
        if name not in deduped:
            deduped[name] = version
    return sorted(deduped.items())


def _extract_dependency_entries_from_text(stdout: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("Legend:", "/", ".")):
            continue
        if not any(char in raw_line for char in ("├", "└", "│", "+", "`")):
            continue
        cleaned = line.lstrip("│├└─+` ")
        token = cleaned.split(maxsplit=1)[0]
        match = _VERSIONED_PACKAGE_RE.match(token)
        if match:
            entries.append((match.group("name"), match.group("version")))
    deduped: dict[str, str] = {}
    for name, version in entries:
        if name not in deduped:
            deduped[name] = version
    return sorted(deduped.items())


def _summarize_dependency_list(tool: str, stdout: str, stderr: str) -> str | None:
    stripped = stdout.strip()
    if not stripped:
        return f"{tool} list: no dependencies"
    entries: list[tuple[str, str]]
    if stripped.startswith(("{", "[")):
        try:
            entries = _extract_dependency_entries_from_json(json.loads(stripped))
        except json.JSONDecodeError:
            return None
    else:
        entries = _extract_dependency_entries_from_text(stripped)

    if not entries:
        return None

    lines = [f"{tool} list: {len(entries)} dependencies"]
    for name, version in entries[:12]:
        suffix = f" ({version})" if version else ""
        lines.append(f"  {name}{suffix}")
    if len(entries) > 12:
        lines.append(f"... +{len(entries) - 12} more dependencies")
    _append_warnings(lines, stderr)
    return "\n".join(lines)


def _summarize_bundle(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return ""

    installed = [
        line.removeprefix("Installing ").strip()
        for line in lines
        if line.startswith("Installing ")
    ]
    fetched = [
        line.removeprefix("Fetching ").strip()
        for line in lines
        if line.startswith("Fetching ") and "gem metadata" not in line
    ]
    warnings = [
        line for line in lines if line.lower().startswith(("warning:", "warn:"))
    ]

    if any("Bundle updated!" in line for line in lines):
        summary = "bundle update: updated"
    elif any("Bundle complete!" in line for line in lines):
        summary = "bundle install: complete"
    else:
        return None

    output = [summary]
    if installed:
        output.append(f"Installed gems: {len(installed)}")
        output.extend(f"  {gem}" for gem in installed[:8])
        if len(installed) > 8:
            output.append(f"... +{len(installed) - 8} more installed gems")
    elif fetched:
        output.append(f"Fetched gems: {len(fetched)}")
        output.extend(f"  {gem}" for gem in fetched[:8])
        if len(fetched) > 8:
            output.append(f"... +{len(fetched) - 8} more fetched gems")
    output.extend(warnings[:5])
    return "\n".join(output)


def _summarize_prisma_generate(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.rstrip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "prisma generate: client generated"

    counts = {"models": 0, "enums": 0, "types": 0}
    output_path: str | None = None
    warnings: list[str] = []
    generated = False

    for line in lines:
        stripped = line.strip()
        if any(char in stripped for char in _BLOCK_ART_CHARS):
            continue
        lowered = stripped.lower()
        if "generated prisma client" in lowered or "prisma client generated" in lowered:
            generated = True
        for match in _PRISMA_COUNT_RE.finditer(lowered):
            kind = match.group("kind")
            if kind.startswith("model"):
                counts["models"] = max(counts["models"], int(match.group("count")))
            elif kind.startswith("enum"):
                counts["enums"] = max(counts["enums"], int(match.group("count")))
            elif kind.startswith("type"):
                counts["types"] = max(counts["types"], int(match.group("count")))
        if "@prisma/client" in stripped:
            output_path = "@prisma/client"
        if lowered.startswith(("warn", "warning:")):
            warnings.append(stripped)

    if not generated and not output_path and not any(counts.values()):
        return None

    output = ["prisma generate: client generated"]
    if any(counts.values()):
        output.append(
            f"models: {counts['models']}, enums: {counts['enums']}, types: {counts['types']}"
        )
    if output_path:
        output.append(f"output: {output_path}")
    output.extend(warnings[:5])
    return "\n".join(output)


def filter_package_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    kind = _command_kind(command)
    if kind is None:
        return filter_generic_output(
            command,
            stdout,
            stderr,
            exit_code,
            max_output_lines=max_output_lines,
        )

    filter_name = _filter_name(*kind)
    clean_stdout = strip_ansi(stdout.replace("\r", "\n")).rstrip()
    clean_stderr = strip_ansi(stderr.replace("\r", "\n")).rstrip()
    if exit_code != 0:
        return make_filter_result(
            _combine_streams(clean_stdout, clean_stderr, exit_code),
            filter_name=filter_name,
            max_output_lines=max_output_lines,
        )

    summary: str | None = None
    if kind == ("pip", "list"):
        summary = _summarize_pip_list(clean_stdout, clean_stderr)
    elif kind == ("pip", "outdated"):
        summary = _summarize_pip_outdated(clean_stdout, clean_stderr)
    elif kind == ("uv", "sync"):
        summary = _summarize_uv_sync(clean_stdout, clean_stderr)
    elif kind in (("npm", "list"), ("pnpm", "list")):
        summary = _summarize_dependency_list(kind[0], clean_stdout, clean_stderr)
    elif kind[0] == "bundle":
        summary = _summarize_bundle(clean_stdout, clean_stderr)
    elif kind == ("prisma", "generate"):
        summary = _summarize_prisma_generate(clean_stdout, clean_stderr)

    if summary is None:
        return make_filter_result(
            _combine_streams(clean_stdout, clean_stderr, exit_code),
            filter_name=filter_name,
            max_output_lines=max_output_lines,
        )
    return make_filter_result(
        summary,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
    )
