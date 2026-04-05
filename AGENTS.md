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
- `uv ruff check`
- `uv ruff format`

If `uv` is unavailable, fall back to `PYTHONPATH=src python3 ...`.

## Testing

Run focused tests after any behavioral change:
- command rewrite cases
- compound command handling
- hook JSON output

- Prefer adding a small regression test whenever a bug is fixed.
- Create tests systematically at function and module level.
- Target 100% coverage for PTK-owned logic.
- Do not write tests for Python/runtime/library behavior that is already guaranteed by the system or a function signature; test PTK behavior, branching, contracts, and failure modes instead.

## Working style

- Keep changes tight and reviewable.
- Use `TODO.md` for active work, follow-ups, and short historical notes.
- When updating `TODO.md`, append each new history note at the end of the `## History` section instead of inserting it at the top.
- In the edit workflow, run `uv ruff check` and `uv ruff format` as the last steps before finishing.
- Avoid writing large grep-able inventories here; keep this file as operating guidance.
