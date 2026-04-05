"""Discover benchmark scenarios from test fixture .meta files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


@dataclass(frozen=True)
class Scenario:
    category: str
    name: str
    command: str
    exit_code: int
    filter_name: str
    fixture_path: Path

    def load(self) -> dict:
        base = self.fixture_path
        stdout = (
            base.with_suffix(".stdout").read_text()
            if base.with_suffix(".stdout").exists()
            else ""
        )
        stderr = (
            base.with_suffix(".stderr").read_text()
            if base.with_suffix(".stderr").exists()
            else ""
        )
        return {"stdout": stdout, "stderr": stderr}


def discover_scenarios(
    *,
    category: str | None = None,
    fixtures_dir: Path = FIXTURES_DIR,
) -> list[Scenario]:
    """Walk fixture directories and yield Scenario objects from .meta files."""
    scenarios: list[Scenario] = []
    if not fixtures_dir.is_dir():
        return scenarios

    dirs = (
        [fixtures_dir / category]
        if category and (fixtures_dir / category).is_dir()
        else sorted(d for d in fixtures_dir.iterdir() if d.is_dir())
    )

    for cat_dir in dirs:
        for meta_file in sorted(cat_dir.glob("*.meta")):
            meta = json.loads(meta_file.read_text())
            base = meta_file.with_suffix("")
            scenarios.append(
                Scenario(
                    category=cat_dir.name,
                    name=base.name,
                    command=meta["command"],
                    exit_code=meta["exit_code"],
                    filter_name=meta["filter_name"],
                    fixture_path=base,
                )
            )

    return scenarios
