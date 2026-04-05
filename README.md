# PTK (Python)

This repository is a Python port of the PTK command rewrite engine.

## Migration direction

- target public CLI: `ptk run <command>`
- target public library API: `from ptk.runner import run_command`
- command rewrite/planning is internal implementation detail
- `rtk/` is read-only reference material, not a compatibility contract
- the current `ptk rewrite` command is transition scaffolding while the new execution-oriented architecture is built

## What it does

- rewrites agent shell commands like `git status` to `ptk git status`
- preserves compound commands such as `&&`, `||`, `;`, and `&`
- exposes a small CLI for use in agent hooks

## Install locally

```bash
pip install -e .
```

## Current scaffold usage

```bash
ptk rewrite "git status"
ptk rewrite "cargo test && git push"
```

Target public usage after the migration work lands:

```bash
ptk run "git status"
```

The package is intentionally small and dependency-free so it can be embedded in
agent toolchains and hook scripts.
