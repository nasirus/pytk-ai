from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(category: str, name: str) -> dict:
    """Load a fixture by category/name, returning command, stdout, stderr, exit_code, filter_name."""
    base = FIXTURES_DIR / category / name
    meta = json.loads(base.with_suffix(".meta").read_text())
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
    return {**meta, "stdout": stdout, "stderr": stderr}


def requires_tool(*tools: str):
    """Skip test if any required tool is not on PATH."""
    missing = [t for t in tools if shutil.which(t) is None]
    return unittest.skipIf(bool(missing), f"requires: {', '.join(missing)}")
