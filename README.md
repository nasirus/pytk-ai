# PTK (Python)

This repository is a Python port of the PTK command rewrite and output-filtering engine.

## Migration direction

- target public CLI: `ptk run <command>`
- target public library API: `from ptk.runner import run_command`
- command rewrite/planning is internal implementation detail
- `rtk/` is read-only reference material, not a compatibility contract
- the old rewrite-first scaffold has been replaced by the execution-oriented `ptk run` flow

## What it does

- plans shell commands internally for PTK-managed handling when useful
- executes raw shell commands through a small Python runner
- filters stdout/stderr into a compact token-efficient result
- preserves compound commands such as `&&`, `||`, `;`, `&`, and simple pipes
- exposes a small CLI plus hook-oriented JSON adapters

## Install locally

```bash
pip install -e .
```

## CLI usage

```bash
ptk run git status
ptk run "cargo test && git push"
```

## Library usage

```python
from ptk.runner import run_command

result = run_command("git status")
print(result.filtered_output)
print(result.exit_code)
```

The package is intentionally small and dependency-free so it can be embedded in
agent toolchains and hook scripts.
