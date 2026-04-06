from __future__ import annotations

import json
import os
from pathlib import Path
import re


_TIMESTAMP_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]?\d*\s*")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_NUM_RE = re.compile(r"\b\d{4,}\b")
_PATH_RE = re.compile(r"/[\w./\-]+")
_CARGO_DEP_RE = re.compile(
    r'^([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]+)"|.*version\s*=\s*"([^"]+)")'
)
_CARGO_SECTION_RE = re.compile(r"^\[([^\]]+)\]")
_REQ_DEP_RE = re.compile(r"^([a-zA-Z0-9_.-]+)([=<>!~]+.*)?$")
_OUTPUT_NUMBER_RE = re.compile(r"(\d+)\s*(passed|failed|skipped|ignored)")

_SENSITIVE_PATTERNS = {
    "key",
    "secret",
    "password",
    "token",
    "credential",
    "auth",
    "private",
    "api_key",
    "apikey",
    "access_key",
    "jwt",
}


def validate_json_extension(path: str | Path) -> str | None:
    file_path = Path(path)
    ext = file_path.suffix.lower().lstrip(".")
    format_name = {
        "toml": "TOML",
        "yaml": "YAML",
        "yml": "YAML",
        "xml": "XML",
        "csv": "CSV",
        "ini": "INI",
        "env": "env",
        "txt": "plain text",
    }.get(ext)
    if format_name is None:
        return None
    message = (
        f"{file_path} is not a JSON file (detected {format_name}). "
        "Use `pytk-ai read` for non-JSON files."
    )
    if file_path.name == "Cargo.toml":
        message += " Tip: use `pytk-ai deps` for Cargo.toml."
    return message


def _compact_json(value: object, depth: int, max_depth: int) -> str:
    indent = "  " * depth
    if depth > max_depth:
        return f"{indent}..."
    if value is None:
        return f"{indent}null"
    if isinstance(value, bool):
        return f"{indent}{str(value).lower()}"
    if isinstance(value, (int, float)):
        return f"{indent}{value}"
    if isinstance(value, str):
        text = value[:77] + "..." if len(value) > 80 else value
        return f'{indent}"{text}"'
    if isinstance(value, list):
        if not value:
            return f"{indent}[]"
        if len(value) > 5:
            first = _compact_json(value[0], depth + 1, max_depth).strip()
            return f"{indent}[{first}, ... +{len(value) - 1} more]"
        if all(not isinstance(item, (list, dict)) for item in value):
            inline = ", ".join(
                _compact_json(item, 0, max_depth).strip() for item in value
            )
            return f"{indent}[{inline}]"
        lines = [f"{indent}["]
        for item in value:
            lines.append(f"{_compact_json(item, depth + 1, max_depth)},")
        lines.append(f"{indent}]")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return f"{indent}{{}}"
        lines = [f"{indent}{{"]
        keys = sorted(value)
        for index, key in enumerate(keys):
            item = value[key]
            if not isinstance(item, (list, dict)):
                lines.append(
                    f"{indent}  {key}: {_compact_json(item, 0, max_depth).strip()}"
                )
            else:
                lines.append(f"{indent}  {key}:")
                lines.append(_compact_json(item, depth + 1, max_depth))
            if index >= 20:
                lines.append(f"{indent}  ... +{len(keys) - index - 1} more keys")
                break
        lines.append(f"{indent}}}")
        return "\n".join(lines)
    return f"{indent}{value}"


def _json_schema(value: object, depth: int, max_depth: int) -> str:
    indent = "  " * depth
    if depth > max_depth:
        return f"{indent}..."
    if value is None:
        return f"{indent}null"
    if isinstance(value, bool):
        return f"{indent}bool"
    if isinstance(value, int):
        return f"{indent}int"
    if isinstance(value, float):
        return f"{indent}float"
    if isinstance(value, str):
        if len(value) > 50:
            return f"{indent}string[{len(value)}]"
        if value.startswith("http"):
            return f"{indent}url"
        if value.count("-") == 2 and len(value) == 10:
            return f"{indent}date?"
        return f"{indent}string"
    if isinstance(value, list):
        if not value:
            return f"{indent}[]"
        first = _json_schema(value[0], depth + 1, max_depth).strip()
        if len(value) == 1:
            return (
                f"{indent}[\n{_json_schema(value[0], depth + 1, max_depth)}\n{indent}]"
            )
        return f"{indent}[{first}] ({len(value)})"
    if isinstance(value, dict):
        if not value:
            return f"{indent}{{}}"
        lines = [f"{indent}{{"]
        keys = sorted(value)
        for index, key in enumerate(keys):
            item = value[key]
            schema = _json_schema(item, depth + 1, max_depth)
            if not isinstance(item, (list, dict)):
                suffix = "," if index < len(keys) - 1 else ""
                lines.append(f"{indent}  {key}: {schema.strip()}{suffix}")
            else:
                lines.append(f"{indent}  {key}:")
                lines.append(schema)
            if index >= 15:
                lines.append(f"{indent}  ... +{len(keys) - index - 1} more keys")
                break
        lines.append(f"{indent}}}")
        return "\n".join(lines)
    return f"{indent}unknown"


def render_json_output(
    content: str, *, max_depth: int = 3, schema_only: bool = False
) -> str:
    value = json.loads(content)
    if schema_only:
        return _json_schema(value, 0, max_depth)
    return _compact_json(value, 0, max_depth)


def _normalize_log_line(line: str) -> str:
    normalized = _TIMESTAMP_RE.sub("", line)
    normalized = _UUID_RE.sub("<UUID>", normalized)
    normalized = _HEX_RE.sub("<HEX>", normalized)
    normalized = _NUM_RE.sub("<NUM>", normalized)
    normalized = _PATH_RE.sub("<PATH>", normalized)
    return normalized.strip()


def render_log_output(content: str) -> str:
    error_counts: dict[str, int] = {}
    warn_counts: dict[str, int] = {}
    info_count = 0
    original_errors: dict[str, str] = {}
    original_warnings: dict[str, str] = {}

    for line in content.splitlines():
        lowered = line.lower()
        normalized = _normalize_log_line(line)
        if any(token in lowered for token in ("error", "fatal", "panic")):
            error_counts[normalized] = error_counts.get(normalized, 0) + 1
            original_errors.setdefault(normalized, line)
        elif "warn" in lowered:
            warn_counts[normalized] = warn_counts.get(normalized, 0) + 1
            original_warnings.setdefault(normalized, line)
        elif "info" in lowered:
            info_count += 1

    lines = [
        "Log Summary",
        f"   [error] {sum(error_counts.values())} errors ({len(error_counts)} unique)",
        f"   [warn] {sum(warn_counts.values())} warnings ({len(warn_counts)} unique)",
        f"   [info] {info_count} info messages",
        "",
    ]
    if error_counts:
        lines.append("[ERRORS]")
        for normalized, count in sorted(
            error_counts.items(), key=lambda item: (-item[1], item[0])
        )[:10]:
            original = original_errors[normalized]
            snippet = original[:97] + "..." if len(original) > 100 else original
            prefix = f"   [x{count}] " if count > 1 else "   "
            lines.append(f"{prefix}{snippet}")
        if len(error_counts) > 10:
            lines.append(f"   ... +{len(error_counts) - 10} more unique errors")
        lines.append("")
    if warn_counts:
        lines.append("[WARNINGS]")
        for normalized, count in sorted(
            warn_counts.items(), key=lambda item: (-item[1], item[0])
        )[:5]:
            original = original_warnings[normalized]
            snippet = original[:97] + "..." if len(original) > 100 else original
            prefix = f"   [x{count}] " if count > 1 else "   "
            lines.append(f"{prefix}{snippet}")
        if len(warn_counts) > 5:
            lines.append(f"   ... +{len(warn_counts) - 5} more unique warnings")
    return "\n".join(lines).rstrip()


def _mask_value(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"


def _is_lang_var(key: str) -> bool:
    patterns = (
        "RUST",
        "CARGO",
        "PYTHON",
        "PIP",
        "NODE",
        "NPM",
        "YARN",
        "DENO",
        "BUN",
        "JAVA",
        "MAVEN",
        "GRADLE",
        "GO",
        "GOPATH",
        "GOROOT",
        "RUBY",
        "GEM",
        "PHP",
        "DOTNET",
        "NUGET",
    )
    upper = key.upper()
    return any(pattern in upper for pattern in patterns)


def _is_cloud_var(key: str) -> bool:
    patterns = (
        "AWS",
        "AZURE",
        "GCP",
        "GOOGLE_CLOUD",
        "DOCKER",
        "KUBERNETES",
        "K8S",
        "HELM",
        "TERRAFORM",
        "VAULT",
    )
    upper = key.upper()
    return any(pattern in upper for pattern in patterns)


def _is_tool_var(key: str) -> bool:
    patterns = (
        "EDITOR",
        "VISUAL",
        "SHELL",
        "TERM",
        "GIT",
        "SSH",
        "GPG",
        "BREW",
        "HOMEBREW",
        "XDG",
        "CLAUDE",
        "ANTHROPIC",
    )
    upper = key.upper()
    return any(pattern in upper for pattern in patterns)


def _is_interesting_var(key: str) -> bool:
    upper = key.upper()
    return any(
        upper.startswith(pattern)
        for pattern in ("HOME", "USER", "LANG", "LC_", "TZ", "PWD", "OLDPWD")
    )


def render_env_output(
    env_vars: dict[str, str], *, filter_text: str | None = None, show_all: bool = False
) -> str:
    vars_sorted = sorted(env_vars.items())
    path_vars: list[tuple[str, str]] = []
    lang_vars: list[tuple[str, str]] = []
    cloud_vars: list[tuple[str, str]] = []
    tool_vars: list[tuple[str, str]] = []
    other_vars: list[tuple[str, str]] = []

    for key, value in vars_sorted:
        if filter_text and filter_text.lower() not in key.lower():
            continue
        is_sensitive = any(pattern in key.lower() for pattern in _SENSITIVE_PATTERNS)
        if is_sensitive and not show_all:
            display_value = _mask_value(value)
        elif len(value) > 100:
            display_value = f"{value[:50]}... ({len(value)} chars)"
        else:
            display_value = value
        entry = (key, display_value)
        if "PATH" in key:
            path_vars.append(entry)
        elif _is_lang_var(key):
            lang_vars.append(entry)
        elif _is_cloud_var(key):
            cloud_vars.append(entry)
        elif _is_tool_var(key):
            tool_vars.append(entry)
        elif filter_text or _is_interesting_var(key):
            other_vars.append(entry)

    lines: list[str] = []
    if path_vars:
        lines.append("PATH Variables:")
        for key, value in path_vars:
            if key == "PATH":
                paths = value.split(":")
                lines.append(f"  PATH ({len(paths)} entries):")
                for path in paths[:5]:
                    lines.append(f"    {path}")
                if len(paths) > 5:
                    lines.append(f"    ... +{len(paths) - 5} more")
            else:
                lines.append(f"  {key}={value}")
    if lang_vars:
        lines.extend(["", "Language/Runtime:"])
        for key, value in lang_vars:
            lines.append(f"  {key}={value}")
    if cloud_vars:
        lines.extend(["", "Cloud/Services:"])
        for key, value in cloud_vars:
            lines.append(f"  {key}={value}")
    if tool_vars:
        lines.extend(["", "Tools:"])
        for key, value in tool_vars:
            lines.append(f"  {key}={value}")
    if other_vars:
        lines.extend(["", "Other:"])
        for key, value in other_vars[:20]:
            lines.append(f"  {key}={value}")
        if len(other_vars) > 20:
            lines.append(f"  ... +{len(other_vars) - 20} more")
    if not filter_text:
        shown = (
            len(path_vars)
            + len(lang_vars)
            + len(cloud_vars)
            + len(tool_vars)
            + min(len(other_vars), 20)
        )
        lines.extend(["", f"Total: {len(vars_sorted)} vars (showing {shown} relevant)"])
    return "\n".join(line for line in lines if line is not None).strip()


def _summarize_cargo(content: str) -> str:
    current_section = ""
    deps: list[str] = []
    dev_deps: list[str] = []
    for line in content.splitlines():
        section_match = _CARGO_SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group(1)
            continue
        dep_match = _CARGO_DEP_RE.match(line)
        if not dep_match:
            continue
        name = dep_match.group(1)
        version = dep_match.group(2) or dep_match.group(3) or "*"
        dep = f"{name} ({version})"
        if current_section == "dependencies":
            deps.append(dep)
        elif current_section == "dev-dependencies":
            dev_deps.append(dep)
    lines: list[str] = []
    if deps:
        lines.append(f"  Dependencies ({len(deps)}):")
        for dep in deps[:10]:
            lines.append(f"    {dep}")
        if len(deps) > 10:
            lines.append(f"    ... +{len(deps) - 10} more")
    if dev_deps:
        lines.append(f"  Dev ({len(dev_deps)}):")
        for dep in dev_deps[:5]:
            lines.append(f"    {dep}")
        if len(dev_deps) > 5:
            lines.append(f"    ... +{len(dev_deps) - 5} more")
    return "\n".join(lines)


def _summarize_package_json(content: str) -> str:
    data = json.loads(content)
    lines: list[str] = []
    name = data.get("name")
    version = data.get("version")
    if isinstance(name, str):
        lines.append(f"  {name} @ {version or '?'}")
    deps = data.get("dependencies") or {}
    if isinstance(deps, dict) and deps:
        lines.append(f"  Dependencies ({len(deps)}):")
        for index, (dep, dep_version) in enumerate(deps.items()):
            if index >= 10:
                lines.append(f"    ... +{len(deps) - 10} more")
                break
            lines.append(f"    {dep} ({dep_version})")
    dev_deps = data.get("devDependencies") or {}
    if isinstance(dev_deps, dict) and dev_deps:
        lines.append(f"  Dev Dependencies ({len(dev_deps)}):")
        for index, dep in enumerate(dev_deps):
            if index >= 5:
                lines.append(f"    ... +{len(dev_deps) - 5} more")
                break
            lines.append(f"    {dep}")
    return "\n".join(lines)


def _summarize_requirements(content: str) -> str:
    deps: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _REQ_DEP_RE.match(stripped)
        if not match:
            continue
        deps.append(f"{match.group(1)}{match.group(2) or ''}")
    lines = [f"  Packages ({len(deps)}):"]
    for dep in deps[:15]:
        lines.append(f"    {dep}")
    if len(deps) > 15:
        lines.append(f"    ... +{len(deps) - 15} more")
    return "\n".join(lines)


def _summarize_pyproject(content: str) -> str:
    in_deps = False
    deps: list[str] = []
    for line in content.splitlines():
        if "dependencies" in line and "[" in line:
            in_deps = True
            continue
        if in_deps:
            stripped = line.strip()
            if stripped == "]":
                break
            stripped = stripped.strip("\"' ,")
            if stripped:
                deps.append(stripped)
    if not deps:
        return ""
    lines = [f"  Dependencies ({len(deps)}):"]
    for dep in deps[:10]:
        lines.append(f"    {dep}")
    if len(deps) > 10:
        lines.append(f"    ... +{len(deps) - 10} more")
    return "\n".join(lines)


def _summarize_gomod(content: str) -> str:
    module_name = ""
    go_version = ""
    deps: list[str] = []
    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("module "):
            module_name = stripped.removeprefix("module ")
        elif stripped.startswith("go "):
            go_version = stripped.removeprefix("go ")
        elif stripped == "require (":
            in_require = True
        elif stripped == ")":
            in_require = False
        elif in_require and not stripped.startswith("//"):
            parts = stripped.split()
            if len(parts) >= 2:
                deps.append(f"{parts[0]} {parts[1]}")
        elif stripped.startswith("require ") and "(" not in stripped:
            deps.append(stripped.removeprefix("require "))
    lines: list[str] = []
    if module_name:
        lines.append(f"  {module_name} (go {go_version})")
    if deps:
        lines.append(f"  Dependencies ({len(deps)}):")
        for dep in deps[:10]:
            lines.append(f"    {dep}")
        if len(deps) > 10:
            lines.append(f"    ... +{len(deps) - 10} more")
    return "\n".join(lines)


def summarize_dependency_directory(path: str | Path) -> tuple[str, str]:
    base_path = Path(path)
    directory = base_path.parent if base_path.is_file() else base_path
    sections: list[str] = []
    raw_parts: list[str] = []
    found = False
    files = (
        ("Cargo.toml", "Rust (Cargo.toml):", _summarize_cargo),
        ("package.json", "Node.js (package.json):", _summarize_package_json),
        ("requirements.txt", "Python (requirements.txt):", _summarize_requirements),
        ("pyproject.toml", "Python (pyproject.toml):", _summarize_pyproject),
        ("go.mod", "Go (go.mod):", _summarize_gomod),
    )
    for file_name, header, summarizer in files:
        file_path = directory / file_name
        if not file_path.exists():
            continue
        found = True
        content = file_path.read_text(encoding="utf-8")
        raw_parts.append(content)
        summary = summarizer(content)
        if summary:
            sections.append(f"{header}\n{summary}")
    if not found:
        return "", f"No dependency files found in {directory}"
    return "\n".join(raw_parts), "\n".join(sections).strip()


def _truncate(text: str, limit: int = 75) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _detect_summary_output_type(output: str, command: str) -> str:
    cmd_lower = command.lower()
    out_lower = output.lower()
    if "test" in cmd_lower or ("passed" in out_lower and "failed" in out_lower):
        return "tests"
    if "build" in cmd_lower or "compile" in cmd_lower or "compiling" in out_lower:
        return "build"
    if any(token in out_lower for token in ("error:", "warn:", "[info]")):
        return "logs"
    if output.lstrip().startswith(("{", "[")):
        return "json"
    lines = [line for line in output.splitlines() if line.strip()]
    if lines and all(
        len(line) < 200 and ("\t" not in line) and len(line.split()) < 10
        for line in lines
    ):
        return "list"
    return "generic"


def render_summary_output(command: str, output: str, success: bool) -> str:
    lines = output.splitlines()
    result = [
        f"{'[ok]' if success else '[FAIL]'} Command: {_truncate(command, 60)}",
        f"   {len(lines)} lines of output",
        "",
    ]
    kind = _detect_summary_output_type(output, command)
    if kind == "tests":
        passed = failed = skipped = 0
        failures: list[str] = []
        for line in lines:
            lowered = line.lower()
            for number, label in _OUTPUT_NUMBER_RE.findall(lowered):
                value = int(number)
                if label == "passed":
                    passed = max(passed, value)
                elif label == "failed":
                    failed = max(failed, value)
                else:
                    skipped = max(skipped, value)
            if "failed" in lowered and "0 failed" not in lowered:
                failures.append(line)
        result.extend(["Test Results:", f"   [ok] {passed} passed"])
        if failed:
            result.append(f"   [FAIL] {failed} failed")
        if skipped:
            result.append(f"   skip {skipped} skipped")
        if failures:
            result.extend(["", "   Failures:"])
            for failure in failures[:5]:
                result.append(f"   * {_truncate(failure, 70)}")
    elif kind == "build":
        errors = sum(
            1
            for line in lines
            if "error" in line.lower() and "0 error" not in line.lower()
        )
        warnings = sum(
            1
            for line in lines
            if "warning" in line.lower() and "0 warning" not in line.lower()
        )
        compiled = sum(
            1
            for line in lines
            if "compiling" in line.lower() or "compiled" in line.lower()
        )
        result.append("Build Summary:")
        if compiled:
            result.append(f"   {compiled} crates/files compiled")
        if errors:
            result.append(f"   [error] {errors} errors")
        if warnings:
            result.append(f"   [warn] {warnings} warnings")
        if not errors and not warnings:
            result.append("   [ok] Build successful")
    elif kind == "logs":
        error_count = sum(
            1
            for line in lines
            if any(token in line.lower() for token in ("error", "fatal"))
        )
        warn_count = sum(1 for line in lines if "warn" in line.lower())
        info_count = sum(1 for line in lines if "info" in line.lower())
        result.extend(
            [
                "Log Summary:",
                f"   [error] {error_count} errors",
                f"   [warn] {warn_count} warnings",
                f"   [info] {info_count} info",
            ]
        )
    elif kind == "json":
        result.append("JSON Output:")
        try:
            result.append(render_json_output(output, max_depth=2, schema_only=True))
        except Exception:
            result.append("   (Invalid JSON)")
    elif kind == "list":
        non_empty = [line for line in lines if line.strip()]
        result.append(f"List ({len(non_empty)} items):")
        for line in non_empty[:10]:
            result.append(f"   * {_truncate(line, 70)}")
        if len(non_empty) > 10:
            result.append(f"   ... +{len(non_empty) - 10} more")
    else:
        result.append("Output:")
        preview = [line for line in lines[:5] if line.strip()]
        for line in preview:
            result.append(f"   {_truncate(line, 75)}")
        if len(lines) > 10:
            result.append("   ...")
            for line in [line for line in lines[-3:] if line.strip()]:
                result.append(f"   {_truncate(line, 75)}")
    return "\n".join(result)


def _smart_language_name(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    mapping = {
        "rs": "Rust",
        "py": "Python",
        "js": "JavaScript",
        "jsx": "JavaScript",
        "ts": "TypeScript",
        "tsx": "TypeScript",
        "go": "Go",
        "java": "Java",
        "rb": "Ruby",
        "sh": "Shell",
        "bash": "Shell",
        "zsh": "Shell",
    }
    return mapping.get(suffix, "Code")


def render_smart_output(content: str, source_path: str | Path) -> str:
    path = Path(source_path)
    language = _smart_language_name(path)
    lines = content.splitlines()
    imports: list[str] = []
    functions: list[str] = []
    structs: list[str] = []
    patterns: list[str] = []
    import_re = re.compile(r"^(?:use\s+([^;]+)|from\s+(\S+)|import\s+(\S+))")
    fn_re = re.compile(r"(?:fn|def|function|func)\s+([a-zA-Z_][a-zA-Z0-9_]*)")
    struct_re = re.compile(
        r"(?:struct|class|interface|enum|trait|type)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    )
    for line in lines:
        stripped = line.strip()
        import_match = import_re.match(stripped)
        if import_match:
            item = next(group for group in import_match.groups() if group)
            item = item.split("::", 1)[0].split(".", 1)[0]
            if item not in imports:
                imports.append(item)
        fn_match = fn_re.search(stripped)
        if fn_match:
            name = fn_match.group(1)
            if name not in {"main", "new"} and name not in functions:
                functions.append(name)
        struct_match = struct_re.search(stripped)
        if struct_match:
            name = struct_match.group(1)
            if name not in structs:
                structs.append(name)
    if "async" in content and "await" in content:
        patterns.append("async")
    if "useState" in content or "useEffect" in content:
        patterns.append("React hooks")
    if "Result<" in content or "anyhow::" in content:
        patterns.append("error handling")
    if "#[test]" in content or "unittest" in content:
        patterns.append("tests")

    component_bits = []
    if functions:
        component_bits.append(f"{len(functions)} fn")
    if structs:
        component_bits.append(f"{len(structs)} struct")
    if component_bits:
        line1 = f"{language} module ({', '.join(component_bits)}) - {len(lines)} lines"
    else:
        line1 = f"{language} code ({len(lines)} lines)"

    details = []
    if imports:
        details.append(f"uses: {', '.join(imports[:3])}")
    if patterns:
        details.append(f"patterns: {', '.join(patterns[:3])}")
    if not details and functions:
        details.append(f"defines: {', '.join(functions[:3])}")
    line2 = " | ".join(details) if details else "General purpose code file"
    return f"{line1}\n{line2}"


def raw_env_text(env_vars: dict[str, str]) -> str:
    return "".join(f"{key}={value}\n" for key, value in sorted(env_vars.items()))


def merged_environment(overrides: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(os.environ)
    if overrides:
        merged.update(overrides)
    return merged
