from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunOptions:
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    plan: bool = True
    excluded_commands: tuple[str, ...] = ()
    max_output_lines: int = 200
