from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FilterResult:
    output: str
    filter_name: str | None = None
    error: str | None = None
    truncated: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CommandResult:
    original_command: str
    executed_command: str
    planned_command: str
    managed: bool
    changed: bool
    stdout: str
    stderr: str
    filtered_output: str
    exit_code: int
    filter_name: str | None = None
    error: str | None = None
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
