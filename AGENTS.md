# AGENTS.md

## Project context

PTK is the Python implementation of the RTK-style command rewrite layer used by agent CLI hooks.
It works by compressing the output of bash commands to reduce tool output token usage.

Core goals:
- rewrite common shell commands into PTK equivalents
- keep hook behavior non-blocking
- remain easy to package and install from PyPI

The legacy Rust implementation lives in `rtk/` and is useful as reference material.

## Tooling

- Python package layout: `src/ptk/`
- CLI entrypoint: `ptk`
- Preferred local runner: `uv`
- Tests: standard library `unittest`
- No mandatory runtime dependencies at the moment

Recommended local commands:
- `uv run --python 3.12 python -m ptk.cli rewrite "git status"`
- `uv run --python 3.12 python -m unittest discover -s tests -v`
- `uv run --python 3.12 python -m compileall src tests`

If `uv` is unavailable, fall back to `PYTHONPATH=src python3 ...`.

## Testing

Run focused tests after any behavioral change:
- command rewrite cases
- compound command handling
- hook JSON output

Prefer adding a small regression test whenever a bug is fixed.

## Working style

- Keep changes tight and reviewable.
- Use `TODO.md` for active work, follow-ups, and short historical notes.
- When updating `TODO.md`, append each new history note at the end of the `## History` section instead of inserting it at the top.
- Avoid writing large grep-able inventories here; keep this file as operating guidance.
