# AGENTS.md

This file provides guidance to coding agent when working with code in this repository.

## Project overview

PYTK-AI is a Python package and CLI that accepts a bash command, executes it, and returns token-efficient filtered output for LLM consumption. It exposes two surfaces: a CLI (`pytk-ai run <command>`) and a library (`from pytk_ai.runner import run_command`). The package is dependency-free and targets PyPI distribution.

## Commands

Preferred local runner is `uv`. If unavailable, fall back to `PYTHONPATH=src python3 ...`.

```bash
# Install locally (editable)
pip install -e .

# Run all tests
python -m unittest discover -s tests

# Run a single test file
python -m unittest tests/test_filters_git.py

# Run a single test case
python -m unittest tests.test_filters_git.TestGitStatusFilter.test_basic

# Lint and format (run before finishing any change)
uv ruff check
uv ruff format

# CLI usage
pytk-ai run "git status"
```

## Architecture

The execution pipeline flows: **input command → plan/normalize → execute subprocess → apply filter → return structured result**.

### Key modules (`src/pytk_ai/`)

- **`runner.py`** — Main entrypoint. `run_command()` orchestrates the full pipeline: plan → execute → filter → return `CommandResult`.
- **`plan/`** — Command planning engine (pure, no subprocess calls):
  - `planner.py` — Decides whether a command gets PYTK-AI-managed filtering or passes through raw.
  - `scanner.py` — Shell-aware tokenization of command strings.
  - `normalize.py` — Normalizes commands into internal execution plans.
  - `rules.py` — Data-driven command-planning rules and prefix metadata.
  - `models.py` — Plan-specific data models (`CommandPlan`, etc.).
- **`filters/`** — Output filtering layer. Each filter module handles a command domain:
  - `base.py` — Base filter interface and registry.
  - `generic.py` — Fallback filter (ANSI stripping, line collapse, progress bar removal).
  - `git.py`, `python.py`, `system.py`, `build.py`, `files.py`, `go.py`, `ruby.py`, `packages.py`, `tests.py` — Command-specific filters.
- **`models.py`** — `CommandResult` structured result object (command, stdout, stderr, filtered_output, exit_code, filter_name).
- **`subprocess_utils.py`** — Subprocess invocation with stdout/stderr capture.
- **`cli.py`** — Thin CLI wrapper delegating to the library.
- **`config.py`** — Configuration (excluded commands, max output lines, timeout).
- **`rewrite.py`** — Legacy rewrite-compatibility module (transitional, not the target API).
- **`data/`** — Static JSON data files for planning rules.

### Reference material

`rtk/` contains the original Rust implementation. It is **read-only reference**, not a compatibility contract. Do not modify it or treat it as the source of truth for Python behavior.

### Implementing new filters

When adding a filter, start by reading the corresponding Rust source in `rtk/` — TOML filters in `rtk/src/filters/*.toml`, programmatic filters in `rtk/src/cmds/` and `rtk/src/core/`. Use their inline tests as the behavioral spec. Port to idiomatic Python, not a line-for-line translation. While porting, critically assess the Rust implementation for missing edge cases, over-broad patterns, or sub-optimal filtering — improve where it makes sense and document any intentional deviation.

## Testing

- Test files mirror the module they test: `test_<package>_<module>.py` (e.g., `src/pytk_ai/filters/git.py` → `tests/test_filters_git.py`).
- When adding a new filter module, create a corresponding test file following this convention.
- Prefer adding a small regression test whenever a bug is fixed.
- Target 100% coverage for PYTK-AI-owned logic. Do not test Python/runtime/library behavior already guaranteed by the system — test PYTK-AI behavior, branching, contracts, and failure modes.

## Conventions

- Planning logic must be pure and testable without subprocesses.
- Filters must fail safe — if filtering breaks, raw output must be recoverable.
- Exit codes from underlying commands must be preserved through the pipeline.
- Prefer small, incremental changes. Record meaningful progress in `TODO.md` (append new history notes at the end of the `## History` section).
- The CLI stays thin; all logic lives in the library layer.
- Keep the package dependency-free (standard library only).
- Run `uv ruff check` and `uv ruff format` as the last steps before finishing any change.
