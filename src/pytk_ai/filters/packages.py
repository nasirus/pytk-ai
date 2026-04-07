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
_PRISMA_MIGRATION_NAME_RE = re.compile(r"\b(20\d{6,}_[A-Za-z0-9_]+)\b")
_PRISMA_DB_PUSH_COUNT_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>tables?|columns?|indexes?|foreign keys?)\b",
    re.IGNORECASE,
)


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
    if parts[:3] == ["uv", "pip", "install"]:
        return "uv", "pip-install"
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
    if parts[:2] in (["npm", "run"], ["npm", "exec"]):
        return "npm", "run"
    if parts[:2] in (["pnpm", "list"], ["pnpm", "ls"]):
        return "pnpm", "list"
    if parts[:2] == ["pnpm", "outdated"]:
        return "pnpm", "outdated"
    if parts[:2] == ["pnpm", "install"]:
        return "pnpm", "install"
    if parts[:2] == ["prisma", "generate"]:
        return "prisma", "generate"
    if parts[:3] == ["prisma", "migrate", "dev"]:
        return "prisma", "migrate-dev"
    if parts[:3] == ["prisma", "migrate", "status"]:
        return "prisma", "migrate-status"
    if parts[:3] == ["prisma", "migrate", "deploy"]:
        return "prisma", "migrate-deploy"
    if parts[:3] == ["prisma", "db", "push"]:
        return "prisma", "db-push"
    if parts[:3] in (["npx", "prisma", "generate"], ["pnpm", "prisma", "generate"]):
        return "prisma", "generate"
    if parts[:4] in (
        ["npx", "prisma", "migrate", "dev"],
        ["pnpm", "prisma", "migrate", "dev"],
    ):
        return "prisma", "migrate-dev"
    if parts[:4] in (
        ["npx", "prisma", "migrate", "status"],
        ["pnpm", "prisma", "migrate", "status"],
    ):
        return "prisma", "migrate-status"
    if parts[:4] in (
        ["npx", "prisma", "migrate", "deploy"],
        ["pnpm", "prisma", "migrate", "deploy"],
    ):
        return "prisma", "migrate-deploy"
    if parts[:4] in (
        ["npx", "prisma", "db", "push"],
        ["pnpm", "prisma", "db", "push"],
    ):
        return "prisma", "db-push"
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
        any(line.startswith(("Audited ", "Checked ")) for line in lines)
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


def _summarize_uv_pip_install(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.rstrip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "uv pip install: ok"

    kept: list[str] = []
    warnings: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("Downloading ", "Using cached ", "Preparing ")):
            continue
        if stripped.lower().startswith(("warning:", "warn[")):
            warnings.append(stripped)
            continue
        kept.append(stripped)

    if (
        any(line.startswith(("Audited ", "Checked ")) for line in lines)
        and len(kept) <= len(warnings) + 2
    ):
        output = ["uv pip install: ok (up to date)"]
        output.extend(warnings[:5])
        return "\n".join(output)

    output = kept[:12] or ["uv pip install: ok"]
    if len(kept) > 12:
        output.append(f"... +{len(kept) - 12} more lines")
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


def _parse_pnpm_outdated(stdout: str) -> list[tuple[str, str, str, str | None]] | None:
    stripped = stdout.strip()
    if not stripped:
        return []
    if stripped.startswith(":"):
        stripped = stripped.split("\n", 1)[1].strip() if "\n" in stripped else ""
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        packages = []
        for name, item in payload.items():
            if not isinstance(item, dict):
                continue
            current = item.get("current")
            latest = item.get("latest")
            wanted = item.get("wanted")
            if name and current and latest:
                packages.append(
                    (name, str(current), str(latest), str(wanted) if wanted else None)
                )
        return sorted(packages)

    packages: list[tuple[str, str, str, str | None]] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith(("Legend:", "Package", "┌", "└", "│"))
            or _TABLE_RULE_RE.match(line)
            or set(line) == {"-"}
        ):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        packages.append((parts[0], parts[1], parts[3], parts[2]))
    return sorted(packages)


def _summarize_pnpm_outdated(stdout: str, stderr: str) -> str | None:
    packages = _parse_pnpm_outdated(stdout)
    if packages is None:
        return None
    if not packages:
        return "pnpm outdated: All packages up to date"
    lines = [f"pnpm outdated: {len(packages)} packages"]
    for name, current, latest, wanted in packages[:15]:
        detail = f"{current} -> {latest}"
        if wanted and wanted != latest:
            detail = f"{current} -> {wanted} (latest {latest})"
        lines.append(f"  {name}: {detail}")
    if len(packages) > 15:
        lines.append(f"... +{len(packages) - 15} more packages")
    _append_warnings(lines, stderr)
    return "\n".join(lines)


def _summarize_pnpm_install(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.rstrip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "pnpm install: ok"

    summary_lines: list[str] = []
    change_lines: list[str] = []
    warnings: list[str] = []
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if (
            stripped.startswith(("Progress:",))
            or " resolved " in lowered
            or " reused " in lowered
        ):
            continue
        if (
            stripped.startswith(("Packages:", "dependencies:"))
            or "packages in" in lowered
        ):
            summary_lines.append(stripped)
            continue
        if stripped.startswith(("+", "-")):
            change_lines.append(stripped)
            continue
        if lowered.startswith(("warning", "warn")):
            warnings.append(stripped)

    output = [*summary_lines[:3], *change_lines[:12]]
    if len(change_lines) > 12:
        output.append(f"... +{len(change_lines) - 12} more packages")
    output.extend(warnings[:5])
    if not output:
        return "pnpm install: ok"
    return "\n".join(output)


def _summarize_npm_run(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines: list[str] = []
    for raw_line in combined.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if stripped.startswith(">") and ("@" in stripped or stripped.startswith("> ")):
            continue
        if lowered.startswith("npm warn") or lowered.startswith("npm notice"):
            continue
        if "⸨" in stripped or "⸩" in stripped:
            continue
        lines.append(stripped)
    if not lines:
        return "npm run: ok"
    return "\n".join(lines[:20])


def _summarize_prisma_migrate_dev(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "prisma migrate dev: applied"

    migration_name: str | None = None
    table_creates = 0
    table_alters = 0
    relation_count = 0
    index_count = 0
    applied = False

    for line in lines:
        if any(char in line for char in _BLOCK_ART_CHARS):
            continue
        if migration_name is None:
            match = _PRISMA_MIGRATION_NAME_RE.search(line)
            if match:
                migration_name = match.group(1)
        upper = line.upper()
        if "CREATE TABLE" in upper:
            table_creates += 1
        if "ALTER TABLE" in upper:
            table_alters += 1
        if "FOREIGN KEY" in upper or "REFERENCES" in upper:
            relation_count += 1
        if "CREATE INDEX" in upper:
            index_count += 1
        lowered = line.lower()
        if "applied" in lowered or "migration(s) applied" in lowered:
            applied = True

    output = ["prisma migrate dev: applied" if applied else "prisma migrate dev"]
    if migration_name:
        output.append(f"migration: {migration_name}")
    changes = []
    if table_creates:
        changes.append(f"+{table_creates} tables")
    if table_alters:
        changes.append(f"~{table_alters} tables")
    if relation_count:
        changes.append(f"+{relation_count} relations")
    if index_count:
        changes.append(f"~{index_count} indexes")
    if changes:
        output.append("changes: " + ", ".join(changes))
    return "\n".join(output)


def _summarize_prisma_migrate_status(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "prisma migrate status: unknown"

    applied_count = 0
    pending_count = 0
    latest_migration: str | None = None
    for line in lines:
        lowered = line.lower()
        if "applied" in lowered:
            for match in re.finditer(r"(\d+)\s+applied", lowered):
                applied_count = max(applied_count, int(match.group(1)))
        if "pending" in lowered or "unapplied" in lowered:
            for match in re.finditer(r"(\d+)\s+(?:pending|unapplied)", lowered):
                pending_count = max(pending_count, int(match.group(1)))
        if latest_migration is None:
            match = _PRISMA_MIGRATION_NAME_RE.search(line)
            if match:
                latest_migration = match.group(1)

    output = [
        f"prisma migrate status: {applied_count} applied, {pending_count} pending"
    ]
    if latest_migration:
        output.append(f"latest: {latest_migration}")
    return "\n".join(output)


def _summarize_prisma_migrate_deploy(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "prisma migrate deploy: 0 migrations"

    deployed = 0
    for line in lines:
        lowered = line.lower()
        for match in re.finditer(r"(\d+)\s+migration(?:s)?", lowered):
            deployed = max(deployed, int(match.group(1)))
        if "applied migration" in lowered:
            deployed += 1
    return f"prisma migrate deploy: {deployed} migrations"


def _summarize_prisma_db_push(stdout: str, stderr: str) -> str | None:
    combined = _combine_streams(stdout, stderr, 0)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return "prisma db push: schema pushed"

    counts = {"tables": 0, "columns": 0, "indexes": 0, "foreign keys": 0}
    for line in lines:
        upper = line.upper()
        if "CREATE TABLE" in upper:
            counts["tables"] += 1
        if "ALTER TABLE" in upper or "ADD COLUMN" in upper:
            counts["columns"] += 1
        if "CREATE INDEX" in upper:
            counts["indexes"] += 1
        if "FOREIGN KEY" in upper or "REFERENCES" in upper:
            counts["foreign keys"] += 1
        for match in _PRISMA_DB_PUSH_COUNT_RE.finditer(line):
            kind = match.group("kind").lower()
            count = int(match.group("count"))
            if kind.startswith("table"):
                counts["tables"] = max(counts["tables"], count)
            elif kind.startswith("column"):
                counts["columns"] = max(counts["columns"], count)
            elif kind.startswith("index"):
                counts["indexes"] = max(counts["indexes"], count)
            else:
                counts["foreign keys"] = max(counts["foreign keys"], count)

    output = ["prisma db push: schema pushed"]
    details = [
        f"tables: {counts['tables']}",
        f"columns: {counts['columns']}",
        f"indexes: {counts['indexes']}",
    ]
    if counts["foreign keys"]:
        details.append(f"foreign keys: {counts['foreign keys']}")
    output.append(", ".join(details))
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
    elif kind == ("uv", "pip-install"):
        summary = _summarize_uv_pip_install(clean_stdout, clean_stderr)
    elif kind in (("npm", "list"), ("pnpm", "list")):
        summary = _summarize_dependency_list(kind[0], clean_stdout, clean_stderr)
    elif kind == ("pnpm", "outdated"):
        summary = _summarize_pnpm_outdated(clean_stdout, clean_stderr)
    elif kind == ("pnpm", "install"):
        summary = _summarize_pnpm_install(clean_stdout, clean_stderr)
    elif kind == ("npm", "run"):
        summary = _summarize_npm_run(clean_stdout, clean_stderr)
    elif kind[0] == "bundle":
        summary = _summarize_bundle(clean_stdout, clean_stderr)
    elif kind == ("prisma", "generate"):
        summary = _summarize_prisma_generate(clean_stdout, clean_stderr)
    elif kind == ("prisma", "migrate-dev"):
        summary = _summarize_prisma_migrate_dev(clean_stdout, clean_stderr)
    elif kind == ("prisma", "migrate-status"):
        summary = _summarize_prisma_migrate_status(clean_stdout, clean_stderr)
    elif kind == ("prisma", "migrate-deploy"):
        summary = _summarize_prisma_migrate_deploy(clean_stdout, clean_stderr)
    elif kind == ("prisma", "db-push"):
        summary = _summarize_prisma_db_push(clean_stdout, clean_stderr)

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
