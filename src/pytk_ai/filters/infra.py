from __future__ import annotations

import json
import re
from collections.abc import Iterable

from ..models import FilterResult
from ..plan.normalize import normalize_absolute_first_token, strip_env_prefix
from .base import collapse_repeated_lines, make_filter_result, strip_ansi
from .generic import _combine_streams, filter_generic_output

_TABLE_SPLIT_RE = re.compile(r"\s{2,}")
_SIZE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>B|KB|MB|GB)", re.I)
_IMAGE_ID_RE = re.compile(r"^[0-9a-f]{6,64}$", re.I)
_AWS_READ_RE = re.compile(
    r"^(?:list|get|describe)(?:-[a-z0-9-]+)?$",
    re.IGNORECASE,
)
_TERRAFORM_NOISE_RE = re.compile(
    r"^(?:"
    r"(?:[^:]+:\s+)?Refreshing state.*|"
    r"Acquiring state lock.*|"
    r"Releasing state lock.*|"
    r"\s*#.*unchanged|"
    r"\s*"
    r")$"
)


def _normalized_command(command: str) -> str:
    _, stripped = strip_env_prefix(command.strip())
    return normalize_absolute_first_token(stripped)


def _command_parts(command: str) -> list[str]:
    normalized = _normalized_command(command)
    parts = normalized.split()
    if parts[:2] == ["pytk-ai", "docker"]:
        return ["docker", *parts[2:]]
    if parts[:2] == ["pytk-ai", "kubectl"]:
        return ["kubectl", *parts[2:]]
    if parts[:2] == ["pytk-ai", "aws"]:
        return ["aws", *parts[2:]]
    if parts[:2] == ["pytk-ai", "terraform"]:
        return ["terraform", *parts[2:]]
    return parts


def _command_kind(command: str) -> tuple[str, str] | None:
    parts = _command_parts(command)
    if not parts:
        return None
    if parts[:2] == ["docker", "ps"]:
        return "docker", "ps"
    if parts[:2] == ["docker", "images"]:
        return "docker", "images"
    if parts[:2] == ["docker", "logs"]:
        return "docker", "logs"
    if parts[:3] == ["docker", "compose", "ps"]:
        return "docker.compose", "ps"
    if parts[:3] == ["docker", "compose", "logs"]:
        return "docker.compose", "logs"
    if parts[:3] == ["docker", "compose", "build"]:
        return "docker.compose", "build"
    if parts[:3] == ["kubectl", "get", "pods"] or parts[:2] == ["kubectl", "pods"]:
        return "kubectl", "pods"
    if parts[:3] == ["kubectl", "get", "services"] or parts[:2] == [
        "kubectl",
        "services",
    ]:
        return "kubectl", "services"
    if parts[:2] == ["kubectl", "logs"]:
        return "kubectl", "logs"
    if parts[:2] == ["terraform", "plan"]:
        return "terraform", "plan"
    if parts[:2] == ["terraform", "validate"]:
        return "terraform", "validate"
    if len(parts) >= 3 and parts[0] == "aws":
        service = parts[1]
        operation = parts[2]
        if service == "s3" and operation == "ls":
            return "aws", "read"
        if service == "sts" and operation == "get-caller-identity":
            return "aws", "read"
        if _AWS_READ_RE.match(operation):
            return "aws", "read"
    return None


def _filter_name(kind: str, subkind: str) -> str:
    return f"{kind}.{subkind}"


def _split_table_line(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped:
        return []
    if "\t" in stripped:
        return [part.strip() for part in stripped.split("\t")]
    return [part.strip() for part in _TABLE_SPLIT_RE.split(stripped) if part.strip()]


def _short_image_name(image: str) -> str:
    return image.split("/")[-1] if image else "-"


def _compact_ports(ports: str) -> str:
    parts = [part.strip() for part in ports.split(",") if part.strip()]
    if not parts:
        return "-"
    values: list[str] = []
    for part in parts:
        left = part.split("->", 1)[0]
        token = left.split(":")[-1].split("/")[0].strip()
        values.append(token or part)
    if len(values) <= 3:
        return ", ".join(values)
    return f"{', '.join(values[:2])}, ... +{len(values) - 2}"


def _parse_size_to_mb(value: str) -> float | None:
    match = _SIZE_RE.search(value.strip())
    if not match:
        return None
    number = float(match.group("value"))
    unit = match.group("unit").upper()
    if unit == "GB":
        return number * 1024.0
    if unit == "MB":
        return number
    if unit == "KB":
        return number / 1024.0
    if unit == "B":
        return number / (1024.0 * 1024.0)
    return None


def _parse_docker_ps(stdout: str) -> list[dict[str, str]] | None:
    containers: list[dict[str, str]] = []
    for raw_line in stdout.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        parts = _split_table_line(line)
        if not parts or parts[0] == "CONTAINER ID":
            continue
        if len(parts) >= 6:
            containers.append(
                {
                    "id": parts[0],
                    "image": parts[1],
                    "status": parts[-3] if len(parts) >= 7 else parts[-2],
                    "ports": parts[-2] if len(parts) >= 7 else "",
                    "name": parts[-1],
                }
            )
        elif len(parts) >= 4:
            containers.append(
                {
                    "id": parts[0],
                    "name": parts[1],
                    "status": parts[2],
                    "image": parts[3],
                    "ports": parts[4] if len(parts) > 4 else "",
                }
            )
    return containers or None


def _summarize_docker_ps(stdout: str) -> str | None:
    containers = _parse_docker_ps(stdout)
    if containers is None:
        return None
    if not containers:
        return "docker ps: 0 containers"
    lines = [f"docker ps: {len(containers)} containers"]
    for container in containers[:15]:
        container_id = container["id"][:12]
        ports = _compact_ports(container.get("ports", ""))
        line = (
            f"  {container_id} {container['name']} "
            f"({_short_image_name(container['image'])}) {container['status']}"
        )
        if ports != "-":
            line += f" [{ports}]"
        lines.append(line)
    if len(containers) > 15:
        lines.append(f"... +{len(containers) - 15} more containers")
    return "\n".join(lines)


def _parse_docker_images(stdout: str) -> list[tuple[str, str]] | None:
    images: list[tuple[str, str]] = []
    for raw_line in stdout.splitlines():
        parts = _split_table_line(raw_line)
        if not parts or parts[0] in {"REPOSITORY", "IMAGE"}:
            continue
        if len(parts) >= 4 and _IMAGE_ID_RE.match(parts[1]):
            images.append((parts[0], parts[2]))
        elif len(parts) >= 5:
            images.append((f"{parts[0]}:{parts[1]}", parts[-1]))
        elif len(parts) >= 2:
            images.append((parts[0], parts[1]))
    return images or None


def _parse_compose_ps(stdout: str) -> list[dict[str, str]] | None:
    services: list[dict[str, str]] = []
    for raw_line in stdout.splitlines():
        parts = _split_table_line(raw_line)
        if not parts or parts[0] == "NAME":
            continue
        if len(parts) >= 5 and parts[-1].startswith(
            (
                "Up ",
                "Exited ",
                "Restarting ",
                "Paused ",
                "Created ",
                "Dead ",
            )
        ):
            status = parts[-1]
            ports = ""
        elif len(parts) >= 6:
            status = parts[-2]
            ports = parts[-1]
        else:
            continue
        services.append(
            {
                "name": parts[0],
                "image": parts[1],
                "status": status,
                "ports": ports,
            }
        )
    return services or None


def _summarize_compose_ps(stdout: str) -> str | None:
    services = _parse_compose_ps(stdout)
    if services is None:
        return None
    lines = [f"docker compose ps: {len(services)} services"]
    for service in services[:20]:
        ports = _compact_ports(service.get("ports", ""))
        line = (
            f"  {service['name']} "
            f"({_short_image_name(service['image'])}) {service['status']}"
        )
        if ports != "-":
            line += f" [{ports}]"
        lines.append(line)
    if len(services) > 20:
        lines.append(f"... +{len(services) - 20} more services")
    return "\n".join(lines)


def _summarize_compose_logs(command: str, stdout: str) -> str:
    target = _first_positional(_command_parts(command), 3)
    return _summarize_log_stream("docker compose logs", target, stdout)


def _summarize_compose_build(stdout: str) -> str | None:
    cleaned = strip_ansi(stdout).replace("\r", "\n")
    if not cleaned.strip():
        return "docker compose build: no output"

    summary_line = None
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if "Building" in line and "FINISHED" in line:
            summary_line = line
            break
    if summary_line is None:
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if "Building" in line:
                summary_line = line
                break

    services: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if "[" not in line or "]" not in line:
            continue
        start = line.find("[")
        end = line.find("]", start + 1)
        if start == -1 or end == -1:
            continue
        bracket = line[start + 1 : end]
        service = bracket.split()[0] if bracket else ""
        if service and service != "+" and service not in services:
            services.append(service)

    step_count = sum(
        1 for line in cleaned.splitlines() if line.lstrip().startswith("=> ")
    )

    lines = [
        f"docker compose build: {summary_line}"
        if summary_line
        else "docker compose build"
    ]
    if services:
        lines.append(f"Services: {', '.join(services)}")
    if step_count:
        lines.append(f"Steps: {step_count}")
    return "\n".join(lines)


def _summarize_docker_images(stdout: str) -> str | None:
    images = _parse_docker_images(stdout)
    if images is None:
        return None
    total_size_mb = 0.0
    seen_size = False
    for _, size in images:
        parsed = _parse_size_to_mb(size)
        if parsed is not None:
            total_size_mb += parsed
            seen_size = True
    total_display = ""
    if seen_size:
        total_display = (
            f" ({total_size_mb / 1024.0:.1f}GB)"
            if total_size_mb >= 1024.0
            else f" ({total_size_mb:.0f}MB)"
        )
    lines = [f"docker images: {len(images)} images{total_display}"]
    for image, size in images[:15]:
        label = image if len(image) <= 50 else f"...{image[-47:]}"
        lines.append(f"  {label} [{size}]")
    if len(images) > 15:
        lines.append(f"... +{len(images) - 15} more images")
    return "\n".join(lines)


def _first_positional(parts: list[str], start: int) -> str | None:
    idx = start
    while idx < len(parts):
        token = parts[idx]
        if token == "--":
            idx += 1
            break
        if token.startswith("-"):
            if token in {"-c", "--container", "-n", "--namespace", "--since", "--tail"}:
                idx += 2
            else:
                idx += 1
            continue
        return token
    return parts[idx] if idx < len(parts) else None


def _summarize_log_stream(prefix: str, target: str | None, text: str) -> str:
    body = collapse_repeated_lines(
        strip_ansi(text.replace("\r", "\n")).rstrip(), max_run=1
    )
    header = prefix if target is None else f"{prefix} {target}"
    if not body.strip():
        return f"{header}: no output"
    return f"{header}:\n{body}"


def _parse_kubectl_json(stdout: str) -> dict[str, object] | None:
    stripped = stdout.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _summarize_kubectl_pods(stdout: str) -> str | None:
    payload = _parse_kubectl_json(stdout)
    if payload is not None and isinstance(payload.get("items"), list):
        pods = payload["items"]
        if not pods:
            return "kubectl pods: 0 pods"
        running = pending = failed = 0
        restarts_total = 0
        issues: list[str] = []
        for pod in pods:
            if not isinstance(pod, dict):
                continue
            metadata = pod.get("metadata", {})
            status = pod.get("status", {})
            namespace = (
                metadata.get("namespace", "-") if isinstance(metadata, dict) else "-"
            )
            name = metadata.get("name", "-") if isinstance(metadata, dict) else "-"
            phase = (
                status.get("phase", "Unknown")
                if isinstance(status, dict)
                else "Unknown"
            )
            statuses = (
                status.get("containerStatuses", []) if isinstance(status, dict) else []
            )
            if isinstance(statuses, list):
                for container in statuses:
                    if isinstance(container, dict):
                        restarts_total += int(container.get("restartCount", 0) or 0)
            if phase == "Running":
                running += 1
            elif phase == "Pending":
                pending += 1
                issues.append(f"{namespace}/{name} Pending")
            else:
                waiting_reason = None
                if isinstance(statuses, list):
                    for container in statuses:
                        if not isinstance(container, dict):
                            continue
                        state = container.get("state", {})
                        waiting = (
                            state.get("waiting", {}) if isinstance(state, dict) else {}
                        )
                        reason = (
                            waiting.get("reason") if isinstance(waiting, dict) else None
                        )
                        if isinstance(reason, str) and (
                            "CrashLoop" in reason or "Error" in reason
                        ):
                            waiting_reason = reason
                            break
                if phase in {"Failed", "Error"} or waiting_reason:
                    failed += 1
                    issues.append(f"{namespace}/{name} {waiting_reason or phase}")
        parts = [f"{running} running"]
        if pending:
            parts.append(f"{pending} pending")
        if failed:
            parts.append(f"{failed} failed")
        if restarts_total:
            parts.append(f"{restarts_total} restarts")
        lines = [f"kubectl pods: {len(pods)} pods ({', '.join(parts)})"]
        for issue in issues[:10]:
            lines.append(f"  {issue}")
        if len(issues) > 10:
            lines.append(f"... +{len(issues) - 10} more issues")
        return "\n".join(lines)

    table_lines = stdout.splitlines()
    has_namespace = any(
        raw_line.split()[:2] == ["NAMESPACE", "NAME"] for raw_line in table_lines
    )
    rows: list[list[str]] = []
    for raw_line in table_lines:
        parts = raw_line.split()
        if not parts or parts[0] in {"NAME", "NAMESPACE"}:
            continue
        rows.append(parts)
    if not rows:
        return None
    issues: list[str] = []
    running = pending = failed = 0
    restarts_total = 0
    for row in rows:
        namespace = row[0] if has_namespace else None
        name = row[1] if has_namespace and len(row) > 1 else row[0]
        status = (
            row[3]
            if has_namespace and len(row) > 3
            else (row[2] if len(row) > 2 else "Unknown")
        )
        restarts = (
            row[4]
            if has_namespace and len(row) > 4
            else (row[3] if len(row) > 3 else "0")
        )
        issue_name = f"{namespace}/{name}" if namespace else name
        try:
            restarts_total += int(restarts)
        except ValueError:
            pass
        if status == "Running":
            running += 1
        elif status == "Pending":
            pending += 1
            issues.append(f"{issue_name} Pending")
        else:
            if (
                "CrashLoop" in status
                or "Error" in status
                or status
                in {
                    "Failed",
                    "Error",
                    "ImagePullBackOff",
                }
            ):
                failed += 1
                issues.append(f"{issue_name} {status}")
            else:
                running += 1
    parts = [f"{running} running"]
    if pending:
        parts.append(f"{pending} pending")
    if failed:
        parts.append(f"{failed} failed")
    if restarts_total:
        parts.append(f"{restarts_total} restarts")
    lines = [f"kubectl pods: {len(rows)} pods ({', '.join(parts)})"]
    for issue in issues[:10]:
        lines.append(f"  {issue}")
    if len(issues) > 10:
        lines.append(f"... +{len(issues) - 10} more issues")
    return "\n".join(lines)


def _summarize_kubectl_services(stdout: str) -> str | None:
    payload = _parse_kubectl_json(stdout)
    if payload is not None and isinstance(payload.get("items"), list):
        services = payload["items"]
        if not services:
            return "kubectl services: 0 services"
        lines = [f"kubectl services: {len(services)} services"]
        for service in services[:15]:
            if not isinstance(service, dict):
                continue
            metadata = service.get("metadata", {})
            spec = service.get("spec", {})
            namespace = (
                metadata.get("namespace", "-") if isinstance(metadata, dict) else "-"
            )
            name = metadata.get("name", "-") if isinstance(metadata, dict) else "-"
            service_type = spec.get("type", "-") if isinstance(spec, dict) else "-"
            ports: list[str] = []
            for port in spec.get("ports", []) if isinstance(spec, dict) else []:
                if not isinstance(port, dict):
                    continue
                service_port = port.get("port")
                target_port = port.get("targetPort", service_port)
                if service_port == target_port:
                    ports.append(str(service_port))
                else:
                    ports.append(f"{service_port}->{target_port}")
            lines.append(f"  {namespace}/{name} {service_type} [{', '.join(ports)}]")
        if len(services) > 15:
            lines.append(f"... +{len(services) - 15} more services")
        return "\n".join(lines)

    table_lines = stdout.splitlines()
    has_namespace = any(
        raw_line.split()[:2] == ["NAMESPACE", "NAME"] for raw_line in table_lines
    )
    rows: list[list[str]] = []
    for raw_line in table_lines:
        parts = raw_line.split()
        if not parts or parts[0] in {"NAME", "NAMESPACE"}:
            continue
        rows.append(parts)
    if not rows:
        return None
    lines = [f"kubectl services: {len(rows)} services"]
    for row in rows[:15]:
        namespace = row[0] if has_namespace else None
        name = row[1] if has_namespace and len(row) > 1 else row[0]
        service_type = (
            row[2]
            if has_namespace and len(row) > 2
            else (row[1] if len(row) > 1 else "-")
        )
        ports = row[-2] if len(row) >= 2 else "-"
        label = f"{namespace}/{name}" if namespace else name
        lines.append(f"  {label} {service_type} [{ports}]")
    if len(rows) > 15:
        lines.append(f"... +{len(rows) - 15} more services")
    return "\n".join(lines)


def _terraform_plan_lines(text: str) -> list[str]:
    return [
        line.rstrip()
        for line in strip_ansi(text.replace("\r", "\n")).splitlines()
        if not _TERRAFORM_NOISE_RE.match(line)
    ]


def _summarize_terraform_plan(stdout: str, stderr: str, exit_code: int) -> str | None:
    combined = _combine_streams(stdout, stderr, exit_code)
    lines = _terraform_plan_lines(combined)
    if not lines:
        return "terraform plan: no changes detected"
    joined = "\n".join(lines)
    if "No changes." in joined:
        return "terraform plan: no changes detected"
    return joined


def _summarize_terraform_validate(
    stdout: str, stderr: str, exit_code: int
) -> str | None:
    combined = strip_ansi(
        _combine_streams(stdout, stderr, exit_code).replace("\r", "\n")
    ).strip()
    if not combined:
        return "terraform validate: ok"
    if exit_code == 0 and "Success! The configuration is valid" in combined:
        return "terraform validate: ok (valid)"
    return combined


def _aws_display_name(parts: list[str]) -> str:
    if len(parts) < 3:
        return "aws"
    return f"aws {parts[1]} {parts[2]}"


def _iter_aws_instances(payload: dict[str, object]) -> Iterable[dict[str, object]]:
    reservations = payload.get("Reservations")
    if not isinstance(reservations, list):
        return ()
    instances: list[dict[str, object]] = []
    for reservation in reservations:
        if not isinstance(reservation, dict):
            continue
        for instance in reservation.get("Instances", []):
            if isinstance(instance, dict):
                instances.append(instance)
    return instances


def _summarize_aws_structured(
    parts: list[str], payload: dict[str, object]
) -> str | None:
    service = parts[1] if len(parts) > 1 else ""
    operation = parts[2] if len(parts) > 2 else ""
    if service == "sts" and operation == "get-caller-identity":
        account = payload.get("Account", "?")
        arn = payload.get("Arn", "?")
        return f"AWS: {account} {arn}"

    if service == "ec2" and operation == "describe-instances":
        instances = list(_iter_aws_instances(payload))
        lines = [f"aws ec2 describe-instances: {len(instances)} instances"]
        for instance in instances[:15]:
            tags = instance.get("Tags", [])
            name = "-"
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                        name = str(tag.get("Value", "-"))
                        break
            lines.append(
                "  "
                + " ".join(
                    [
                        str(instance.get("InstanceId", "?")),
                        str(instance.get("State", {}).get("Name", "?"))
                        if isinstance(instance.get("State"), dict)
                        else "?",
                        str(instance.get("InstanceType", "?")),
                        str(instance.get("PrivateIpAddress", "-")),
                        f"({name})",
                    ]
                )
            )
        if len(instances) > 15:
            lines.append(f"... +{len(instances) - 15} more instances")
        return "\n".join(lines)

    collection_keys = (
        "Stacks",
        "StackSummaries",
        "DBInstances",
        "services",
        "serviceArns",
        "Buckets",
        "Contents",
    )
    for key in collection_keys:
        value = payload.get(key)
        if isinstance(value, list):
            lines = [f"{_aws_display_name(parts)}: {len(value)} items"]
            for item in value[:10]:
                if isinstance(item, str):
                    lines.append(f"  {item.split('/')[-1]}")
                    continue
                if not isinstance(item, dict):
                    lines.append(f"  {item}")
                    continue
                preferred = [
                    item.get("StackName"),
                    item.get("DBInstanceIdentifier"),
                    item.get("serviceName"),
                    item.get("Name"),
                    item.get("Key"),
                    item.get("Id"),
                    item.get("InstanceId"),
                ]
                label = next(
                    (str(candidate) for candidate in preferred if candidate), None
                )
                state = next(
                    (
                        str(candidate)
                        for candidate in (
                            item.get("StackStatus"),
                            item.get("DBInstanceStatus"),
                            item.get("status"),
                            item.get("State"),
                        )
                        if candidate
                    ),
                    None,
                )
                if label and state:
                    lines.append(f"  {label} {state}")
                elif label:
                    lines.append(f"  {label}")
                else:
                    preview = ", ".join(
                        f"{name}={value}"
                        for name, value in list(item.items())[:3]
                        if not isinstance(value, (dict, list))
                    )
                    lines.append(f"  {preview or '<object>'}")
            if len(value) > 10:
                lines.append(f"... +{len(value) - 10} more items")
            return "\n".join(lines)

    scalar_pairs = [
        f"{key}={value}"
        for key, value in list(payload.items())[:6]
        if not isinstance(value, (dict, list))
    ]
    if scalar_pairs:
        return f"{_aws_display_name(parts)}: " + ", ".join(scalar_pairs)
    return None


def _summarize_aws_read(command: str, stdout: str) -> str | None:
    parts = _command_parts(command)
    if len(parts) >= 3 and parts[1:3] == ["s3", "ls"]:
        items = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not items:
            return "aws s3 ls: 0 items"
        lines = [f"aws s3 ls: {len(items)} items"]
        lines.extend(f"  {line}" for line in items[:20])
        if len(items) > 20:
            lines.append(f"... +{len(items) - 20} more items")
        return "\n".join(lines)

    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _summarize_aws_structured(parts, payload)


def filter_infra_output(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    max_output_lines: int = 200,
) -> FilterResult:
    kind = _command_kind(command)
    generic = filter_generic_output(
        command,
        stdout,
        stderr,
        exit_code,
        max_output_lines=max_output_lines,
    )
    if kind is None:
        return FilterResult(
            output=generic.output,
            filter_name="infra",
            error=generic.error,
            truncated=generic.truncated,
        )

    category, subkind = kind
    filter_name = _filter_name(category, subkind)
    if exit_code != 0 and not (category == "terraform" and subkind == "plan"):
        return FilterResult(
            output=generic.output,
            filter_name=filter_name,
            error=generic.error,
            truncated=generic.truncated,
        )

    summary: str | None
    if kind == ("docker", "ps"):
        summary = _summarize_docker_ps(stdout)
    elif kind == ("docker", "images"):
        summary = _summarize_docker_images(stdout)
    elif kind == ("docker", "logs"):
        target = _first_positional(_command_parts(command), 2)
        summary = _summarize_log_stream("docker logs", target, stdout)
    elif kind == ("docker.compose", "ps"):
        summary = _summarize_compose_ps(stdout)
    elif kind == ("docker.compose", "logs"):
        summary = _summarize_compose_logs(command, stdout)
    elif kind == ("docker.compose", "build"):
        summary = _summarize_compose_build(stdout)
    elif kind == ("kubectl", "pods"):
        summary = _summarize_kubectl_pods(stdout)
    elif kind == ("kubectl", "services"):
        summary = _summarize_kubectl_services(stdout)
    elif kind == ("kubectl", "logs"):
        target = _first_positional(_command_parts(command), 2)
        summary = _summarize_log_stream("kubectl logs", target, stdout)
    elif kind == ("aws", "read"):
        summary = _summarize_aws_read(command, stdout)
    elif kind == ("terraform", "plan"):
        summary = _summarize_terraform_plan(stdout, stderr, exit_code)
    elif kind == ("terraform", "validate"):
        summary = _summarize_terraform_validate(stdout, stderr, exit_code)
    else:
        summary = None

    if summary is None:
        return FilterResult(
            output=generic.output,
            filter_name=filter_name,
            error=generic.error,
            truncated=generic.truncated,
        )

    return make_filter_result(
        summary,
        filter_name=filter_name,
        max_output_lines=max_output_lines,
        error=generic.error,
    )
