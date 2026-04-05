# TODO

## Active work

- Define the PTK high-level architecture around an internal planning step plus public execute + strip library/CLI flow.
- Turn the first next-priority item into a full project plan in `PLAN.md`, centered on internal planning/rewrite and public `ptk run` / `run_command` surfaces.


## Next priorities

1. Decompose the architecture into a set of Python modules and classes that can be implemented incrementally.
2. Implement the core command rewrite flow in Python, using the existing Rust code as a reference for logic and behavior.

## History

- 2026-04-05: Created the initial Python PTK scaffold, renamed the package from `rtk` to `ptk`, and verified the core rewrite flow.
- 2026-04-05: Added the first hook JSON responses for Claude and Cursor.
- 2026-04-05: Added token-frugal mode guidance to `INSTRUCTIONS.md`, then tightened it into a brief XML-tagged prompt block.
- 2026-04-05: Simplified `ARCHITECTURE.md` so `ptk run` is the main public interface and command rewrite remains an internal planning step rather than a required public CLI feature.
- 2026-04-05: Added `ARCHITECTURE.md` to define the PTK target architecture as a Python library/CLI for command rewrite, execution, and stripped output.
- 2026-04-05: Added `PLAN.md` with a detailed isolated checklist for decomposing the architecture into incremental modules/classes for later parallel execution.
- 2026-04-05: Rewrote `PLAN.md` as a full task plan for the new Python-first PTK architecture, explicitly treating rewrite as internal and `ptk run` as the public CLI surface, without legacy Rust compatibility requirements.
- 2026-04-05: Added a workflow rule in `AGENTS.md` to append new `TODO.md` history notes at the end of the `## History` section.
- 2026-04-05: Added testing guidance to `AGENTS.md` and `PLAN.md` to create systematic function/module tests, target 100% PTK-owned coverage, and avoid testing system or signature-guaranteed behavior.
- 2026-04-05: Added edit-workflow guidance to `AGENTS.md` and `PLAN.md` to run `uv ruff check` and `uv ruff format` as the last steps before finishing.
- 2026-04-05: Scoped the `uv ruff check` / `uv ruff format` workflow instruction to `AGENTS.md` only and removed it from `PLAN.md`.