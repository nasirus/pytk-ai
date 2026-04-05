from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ptk.runner import run_command  # noqa: E402


class Scenario(NamedTuple):
    title: str
    command: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(title="List repository root", command="ls"),
    Scenario(title="List PTK package files", command="ls src/ptk"),
    Scenario(title="Grep PTK mentions in README", command="grep -n 'ptk' README.md"),
    Scenario(title="Show tracked git status", command="git status --short"),
    Scenario(title="Show latest git commit", command="git log -1 --oneline"),
    Scenario(
        title="Print a simple file-manipulation pipeline",
        command="ls src/ptk | grep '\\.py$'",
    ),
)


def run_bash(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )


def show_section(title: str, content: str) -> None:
    print(title)
    if content:
        print(content, end="" if content.endswith("\n") else "\n")
    else:
        print("<empty>")


def main() -> None:
    for index, scenario in enumerate(SCENARIOS, start=1):
        bash_result = run_bash(scenario.command)
        ptk_result = run_command(scenario.command, cwd=str(PROJECT_ROOT))

        print(f"Scenario {index}: {scenario.title}")
        print(f"Command: {scenario.command}")
        print()
        print("=== bash subprocess ===")
        print(f"exit_code: {bash_result.returncode}")
        show_section("stdout:", bash_result.stdout)
        show_section("stderr:", bash_result.stderr)
        print()
        print("=== ptk ===")
        print(f"exit_code: {ptk_result.exit_code}")
        print(f"executed_command: {ptk_result.executed_command}")
        print(f"planned_command: {ptk_result.planned_command}")
        print(f"managed: {ptk_result.managed}")
        show_section("filtered_output:", ptk_result.filtered_output)
        show_section("stdout:", ptk_result.stdout)
        show_section("stderr:", ptk_result.stderr)
        if index != len(SCENARIOS):
            print("\n" + "=" * 72 + "\n")


if __name__ == "__main__":
    main()
