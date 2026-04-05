# TODO

## Active work

- Plan implementation complete.
- Keep future follow-up work outside the completed `PLAN.md` baseline unless new requirements land.


## Next priorities

1. Add more command-specific filters only when they deliver clear token savings.
2. Expand hook integration only after concrete product requirements appear.

## History

- 2026-04-05: Created the initial Python PYTK-AI scaffold, renamed the package from `rtk` to `pytk-ai`, and verified the core rewrite flow.
- 2026-04-05: Added the first hook JSON responses for Claude and Cursor.
- 2026-04-05: Added token-frugal mode guidance to `INSTRUCTIONS.md`, then tightened it into a brief XML-tagged prompt block.
- 2026-04-05: Simplified `ARCHITECTURE.md` so `pytk-ai run` is the main public interface and command rewrite remains an internal planning step rather than a required public CLI feature.
- 2026-04-05: Added `ARCHITECTURE.md` to define the PYTK-AI target architecture as a Python library/CLI for command rewrite, execution, and stripped output.
- 2026-04-05: Added `PLAN.md` with a detailed isolated checklist for decomposing the architecture into incremental modules/classes for later parallel execution.
- 2026-04-05: Rewrote `PLAN.md` as a full task plan for the new Python-first PYTK-AI architecture, explicitly treating rewrite as internal and `pytk-ai run` as the public CLI surface, without legacy Rust compatibility requirements.
- 2026-04-05: Added a workflow rule in `AGENTS.md` to append new `TODO.md` history notes at the end of the `## History` section.
- 2026-04-05: Added testing guidance to `AGENTS.md` and `PLAN.md` to create systematic function/module tests, target 100% PYTK-AI-owned coverage, and avoid testing system or signature-guaranteed behavior.
- 2026-04-05: Added edit-workflow guidance to `AGENTS.md` and `PLAN.md` to run `uv ruff check` and `uv ruff format` as the last steps before finishing.
- 2026-04-05: Scoped the `uv ruff check` / `uv ruff format` workflow instruction to `AGENTS.md` only and removed it from `PLAN.md`.
- 2026-04-05: Completed Phase 0 direction reset in `ARCHITECTURE.md`, `PLAN.md`, `TODO.md`, and `README.md`; clarified that `pytk-ai run` / `run_command` are the migration targets, `rtk/` is reference-only, and `src/pytk_ai/rewrite.py` is transitional rather than a required compatibility facade.
- 2026-04-05: Implemented the new PYTK-AI architecture across `pytk_ai.plan`, `pytk_ai.filters`, `pytk_ai.runner`, and the `pytk-ai run` CLI; replaced rewrite-first tests with planner/runner/filter/CLI coverage, refreshed docs/package metadata, and checked off the completed plan stages while leaving only explicit coverage-target validation open.
- 2026-04-05: Validated PYTK-AI-owned coverage with `python -m trace --count --summary`, confirmed 100% execution coverage for the implemented PYTK-AI modules under the new test suite, and closed the remaining `PLAN.md` coverage checklist items.
- 2026-04-05: Added a `labs/` sandbox with a small script that compares classic bash subprocess output against PYTK-AI output for the same command.
- 2026-04-05: Expanded the `labs/` comparison script into a multi-scenario runner covering file listing, grep, and git-oriented command cases.
- 2026-04-05: Extended `labs/compare_bash_and_pytk_ai.py` with a reproducible benchmark mode that measures bash vs PYTK-AI runtime overhead and estimated token savings on large `ls`, `find`, and `git status` scenarios.
- 2026-04-05: Added a high-volume repetitive-output scenario and per-scenario token stats to `labs/compare_bash_and_pytk_ai.py` so token savings are obvious in the default side-by-side comparison mode.
- 2026-04-05: Added `ADD-FILTER-PLAN.md` to track the missing high-value filters, implementation phases, and done criteria for future PYTK-AI sessions.
- 2026-04-05: Updated `ADD-FILTER-PLAN.md` to require future filter work to consult the legacy `/rtk` repository docs and implementations before reimplementing filters in Python.
- 2026-04-05: Updated `ADD-FILTER-PLAN.md` to require future filters to stay modular inside `src/pytk_ai/filters/`, with shared logic isolated and dispatch kept in `filters/__init__.py`.
- 2026-04-05: Completed `ADD-FILTER-PLAN.md` Phase 1 by adding modular high-value git, test-wrapper, cargo-test, ruff-check, and read-command filters; expanded planner coverage for generic `* test` wrappers; and added focused regression tests for the new success/failure paths.
- 2026-04-05: Fixed Phase 1 regressions by limiting the test filter to `cargo test`, preserving full `git branch -vv` local branch lines, and keeping exit-0 `git add` warnings visible.
- 2026-04-05: Completed `ADD-FILTER-PLAN.md` Phase 2 by adding modular build/lint/test filters for cargo build/clippy/fmt, richer mypy and pytest summaries, ESLint/Biome/TypeScript/Next.js grouping, Go and golangci-lint summaries, and Ruby RuboCop/RSpec failure-oriented output with focused regression coverage.
- 2026-04-05: Fixed Phase 2 regressions by keeping unsupported `go ...` commands on the generic filter path and preserving raw Next.js compiler diagnostics when `next build` fails before any route summary is available.
- 2026-04-05: Completed `ADD-FILTER-PLAN.md` Phase 3 by adding modular file/search filters for `read`, `rg`/`grep`, `find`, `tree`, `wc`, and `diff`; expanded rewrite/filter recognition for the new commands; and added Phase 3 regression coverage for summary and raw-error paths.
- 2026-04-05: Fixed Phase 3 regressions by limiting repeated-line collapsing to real `tail` reads, normalizing env-prefixed and absolute file/search commands before filter dispatch, and deriving `wc` metric labels from parsed flags instead of raw column count.
- 2026-04-05: Completed `ADD-FILTER-PLAN.md` Phase 4 by adding a dedicated package-manager filter module for `pip list`/outdated, `uv sync`, `npm`/`pnpm list`, `bundle install`, and `prisma generate`; tightening planner recognition to those command forms; and adding focused success/failure regressions.
- 2026-04-05: Completed `ADD-FILTER-PLAN.md` Phase 5 by adding a dedicated infra filter module for Docker, `docker compose ps`, kubectl pod/service/log views, structured AWS read commands, and Terraform `plan`/`validate`; tightening planner/rule recognition to those Phase 5 command forms; and adding focused regressions for success and raw-failure paths.
