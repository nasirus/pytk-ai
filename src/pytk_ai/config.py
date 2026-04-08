from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class RunOptions:
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    plan: bool = True
    excluded_commands: tuple[str, ...] = ()
    max_output_lines: int = 200
