# TODO

## Active work

- Plan implementation complete.
- Keep future follow-up work outside the completed `PLAN.md` baseline unless new requirements land.


## Next priorities

1. Add more command-specific filters only when they deliver clear token savings.
2. Expand hook integration only after concrete product requirements appear.

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
- 2026-04-05: Completed Phase 0 direction reset in `ARCHITECTURE.md`, `PLAN.md`, `TODO.md`, and `README.md`; clarified that `ptk run` / `run_command` are the migration targets, `rtk/` is reference-only, and `src/ptk/rewrite.py` is transitional rather than a required compatibility facade.
- 2026-04-05: Implemented the new PTK architecture across `ptk.plan`, `ptk.filters`, `ptk.runner`, and the `ptk run` CLI; replaced rewrite-first tests with planner/runner/filter/CLI coverage, refreshed docs/package metadata, and checked off the completed plan stages while leaving only explicit coverage-target validation open.
- 2026-04-05: Validated PTK-owned coverage with `python -m trace --count --summary`, confirmed 100% execution coverage for the implemented PTK modules under the new test suite, and closed the remaining `PLAN.md` coverage checklist items.