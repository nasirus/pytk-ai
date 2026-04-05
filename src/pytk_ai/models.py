from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


FilterUsageMode = Literal["interactive", "hook"]


@dataclass(frozen=True)
class OutputMetrics:
    chars: int
    lines: int
    tokens: int


@dataclass(frozen=True)
class FilterPolicy:
    summary_scope: Literal["success-only", "failure-only", "both"]
    usage_mode_behavior: Literal["same-output"]
    notes: str | None = None


@dataclass(frozen=True)
class FilterMetrics:
    usage_mode: FilterUsageMode
    estimator: str
    raw: OutputMetrics
    filtered: OutputMetrics
    saved_chars: int
    saved_lines: int
    saved_tokens: int
    saved_pct: float


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
    metrics: FilterMetrics | None = None
    policy: FilterPolicy | None = None

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
    filter_metrics: FilterMetrics | None = None
    filter_policy: FilterPolicy | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
