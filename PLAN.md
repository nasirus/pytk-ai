# PLAN

## Frozen project decisions

- PYTK-AI is a new Python project, not a compatibility layer for the Rust tree.
- `rtk/` is reference-only.
- No backward-compatibility work is required for the legacy Rust library or CLI shape.
- Public CLI surface should converge on `pytk-ai run <command>`.
- Command rewrite/planning remains internal implementation detail.
- Public Python API should converge on execute-and-strip entrypoints, not public rewrite entrypoints.
- Testing is systematic at function and module level, with a target of 100% coverage for PYTK-AI-owned logic.
- Tests should not restate guarantees already provided by Python, the standard library, or a function signature; they should focus on PYTK-AI behavior, branching, contracts, and failure modes.

## Target end state

### Public surfaces

- CLI:
  - `pytk-ai run <command>`
- Library:
  - `from pytk_ai.runner import run_command`
- Optional lower-level internal APIs:
  - `pytk_ai.plan.plan_command`
  - `pytk_ai.filters.filter_output`
  - `pytk_ai.subprocess_utils.execute_raw`

### Internal package map

- `src/pytk_ai/__init__.py`
- `src/pytk_ai/__main__.py`
- `src/pytk_ai/cli.py`
- `src/pytk_ai/models.py`
- `src/pytk_ai/config.py`
- `src/pytk_ai/runner.py`
- `src/pytk_ai/subprocess_utils.py`
- `src/pytk_ai/plan/__init__.py`
- `src/pytk_ai/plan/models.py`
- `src/pytk_ai/plan/scanner.py`
- `src/pytk_ai/plan/normalize.py`
- `src/pytk_ai/plan/rules.py`
- `src/pytk_ai/plan/planner.py`
- `src/pytk_ai/filters/__init__.py`
- `src/pytk_ai/filters/base.py`
- `src/pytk_ai/filters/generic.py`
- `src/pytk_ai/filters/system.py`
- `src/pytk_ai/filters/git.py`
- `src/pytk_ai/filters/python.py`
- `src/pytk_ai/data/__init__.py`
- `src/pytk_ai/data/rules.json`

### Core models to introduce

- `Rule`
- `PlanSegment`
- `CommandPlan`
- `ExecutionResult`
- `FilterResult`
- `CommandResult`
- optional `RunOptions`

## Full project plan

### Phase 0 — reset the public direction

- [x] Confirm `ARCHITECTURE.md` remains aligned with the simplified direction: rewrite internal, `pytk-ai run` public, library-first execute-and-strip flow.
- [x] Remove the assumption that `pytk-ai rewrite` must remain public.
- [x] Remove the assumption that `src/pytk_ai/rewrite.py` must remain a compatibility facade.
- [x] Record in docs and task notes that Rust behavior is reference input, not a compatibility contract.
- [x] Define the current migration target as “build the Python architecture cleanly from scratch while reusing only useful logic”.

### Phase 1 — decompose the current code into architecture-ready modules

#### Goal

Split the current `src/pytk_ai/rewrite.py` logic into pure planning modules that can be tested and evolved independently.

#### Tasks

- [x] Inventory the current responsibilities in `src/pytk_ai/rewrite.py`:
  - rule loading
  - env-prefix handling
  - redirect stripping/preservation
  - absolute-path normalization
  - rule matching
  - `head`/`tail` rewrite logic
  - compound command scanning
  - segment orchestration
  - public rewrite result shape
- [x] Create `src/pytk_ai/plan/` package.
- [x] Move planning dataclasses into `src/pytk_ai/plan/models.py`.
- [x] Move rule loading/compilation into `src/pytk_ai/plan/rules.py`.
- [x] Move normalization helpers into `src/pytk_ai/plan/normalize.py`.
- [x] Move compound command scanning into `src/pytk_ai/plan/scanner.py`.
- [x] Move segment rewrite orchestration into `src/pytk_ai/plan/planner.py`.
- [x] Replace direct `rewrite_*` naming in the internal architecture with planning-oriented names where useful.
- [x] Keep planning pure: no subprocess calls, no filtering, no CLI printing.
- [x] Decide whether `src/pytk_ai/rewrite.py` is deleted outright or replaced temporarily during transition.
- [x] Add `src/pytk_ai/plan/__init__.py` exports only for internal planning primitives actually needed elsewhere.

#### Definition of done

- [x] No single planning file owns unrelated concerns.
- [x] Rule loading exists in one place only.
- [x] Planner imports flow one direction: models/data -> helpers -> planner.
- [x] Planning modules are testable without subprocesses.

### Phase 2 — define stable result and configuration models

#### Goal

Create the structured contracts needed by the future runner and CLI.

#### Tasks

- [x] Add `src/pytk_ai/models.py`.
- [x] Define `ExecutionResult` with raw stdout/stderr/exit code/executed command.
- [x] Define `FilterResult` with filtered output/filter name/error metadata.
- [x] Define `CommandResult` with original command, executed command, rewritten/planned flags, raw outputs, filtered output, exit code, and error field.
- [x] Define minimal option/config structures needed by `run_command`.
- [x] Keep models serialization-safe and CLI-friendly.
- [x] Decide whether plan-layer models stay in `pytk_ai.plan.models` and run-layer models stay in `pytk_ai.models`.

#### Definition of done

- [x] Runner and CLI can share the same result object.
- [x] No caller needs to parse CLI text to consume PYTK-AI output.

### Phase 3 — build the internal planning API

#### Goal

Expose an internal `plan_command` flow that transforms raw command text into a reusable command plan.

#### Tasks

- [x] Define `CommandPlan` fields.
- [x] Decide whether plan output stores:
  - original command
  - normalized command
  - planned command to execute
  - whether PYTK-AI-managed path was selected
  - matched rule/filter hints
  - skip reason when unsupported
- [x] Implement `plan_command(command, excluded=None)` in `src/pytk_ai/plan/planner.py`.
- [x] Preserve current high-value rewrite behavior where still relevant to the internal planner.
- [x] Preserve shell-sensitive cases already handled well: quoting, compound ops, redirect suffixes, env prefixes.
- [x] Add explicit skip reasons instead of silent `None` where it helps debugging and tests.
- [x] Ensure planner can express both “PYTK-AI-managed execution path” and “raw shell fallback”.
- [x] Ensure planner can later carry filter hints without re-parsing command text downstream.

#### Definition of done

- [x] Planner is the single source of truth for command normalization/selection.
- [x] Runner can consume planner output directly.

### Phase 4 — build subprocess execution layer

#### Goal

Separate command execution from planning and filtering.

#### Tasks

- [x] Add `src/pytk_ai/subprocess_utils.py`.
- [x] Implement `execute_raw(...)` helper with cwd/env/timeout support.
- [x] Decide exact subprocess invocation strategy for planned PYTK-AI-managed commands versus raw shell fallback.
- [x] Capture stdout, stderr, exit code, and executed command.
- [x] Preserve underlying exit code.
- [x] Make timeout and execution failures explicit in result objects.
- [x] Keep execution layer independent from filter selection logic.

#### Definition of done

- [x] Raw execution can be tested separately from planner and filters.
- [x] Execution errors do not corrupt stdout/stderr capture contracts.

### Phase 5 — build filtering layer

#### Goal

Return compact useful output after execution.

#### Tasks

- [x] Add `src/pytk_ai/filters/` package.
- [x] Add `src/pytk_ai/filters/base.py` for shared filter interfaces/helpers.
- [x] Add `src/pytk_ai/filters/generic.py` with a small generic fallback:
  - ANSI stripping
  - repeated-line collapse
  - progress/noise reduction
  - output truncation policy
- [x] Decide generic stderr policy for success vs failure cases.
- [x] Add command-specific filter modules incrementally:
  - `src/pytk_ai/filters/system.py`
  - `src/pytk_ai/filters/git.py`
  - `src/pytk_ai/filters/python.py`
- [x] Define filter selection strategy from plan hints first, command matching second.
- [x] Ensure filter failure falls back to raw output safely.

#### Definition of done

- [x] Generic fallback works even when no command-specific filter exists.
- [x] Filtering cannot hide the underlying exit code.

### Phase 6 — build `run_command`

#### Goal

Implement the main public library entrypoint.

#### Tasks

- [x] Add `src/pytk_ai/runner.py`.
- [x] Implement `run_command(command, *, cwd=None, env=None, timeout=None, rewrite=True)` or rename the flag to something architecture-consistent like `plan=True`.
- [x] Runner flow must be:
  1. call planner
  2. choose PYTK-AI-managed or raw execution path
  3. execute
  4. filter
  5. return `CommandResult`
- [x] Ensure runner preserves original command and actual executed command.
- [x] Ensure raw output remains available even if filtering fails.
- [x] Ensure runner returns structured errors rather than raising for normal command failures.

#### Definition of done

- [x] `run_command` is the primary stable library interface.
- [x] CLI can delegate almost entirely to runner.

### Phase 7 — simplify the CLI to `pytk-ai run`

#### Goal

Make CLI a thin wrapper around the library.

#### Tasks

- [x] Refactor `src/pytk_ai/cli.py` around `pytk-ai run`.
- [x] Remove public `rewrite` subcommand.
- [x] Decide whether hook support stays now or moves behind internal/secondary subcommands later.
- [x] Ensure `pytk-ai run <command>` joins command args safely and sends them to `run_command`.
- [x] Print filtered output by default.
- [x] Exit with underlying command exit code.
- [x] Keep CLI argument parsing thin; do not re-implement planning or filtering in CLI.

#### Definition of done

- [x] The CLI is a small adapter over the library.
- [x] Public CLI behavior matches the architecture doc.

### Phase 8 — tests and regression coverage

#### Goal

Restructure tests around the new architecture and keep each work area isolated.

#### Tasks

- [x] Treat test creation as required work for every new module and every non-trivial function.
- [x] Aim for 100% coverage across PYTK-AI-owned logic.
- [x] Do not add tests that only re-verify Python/runtime/stdlib guarantees or obvious type-signature behavior; spend coverage budget on PYTK-AI-specific logic, branches, contracts, and failure modes.
- [x] Replace `tests/test_rewrite.py` with architecture-aligned tests.
- [x] Add planning-focused tests:
  - `tests/test_plan_rules.py`
  - `tests/test_plan_normalize.py`
  - `tests/test_plan_scanner.py`
  - `tests/test_plan_planner.py`
- [x] Add runner tests:
  - `tests/test_runner.py`
- [x] Add filter tests:
  - `tests/test_filters_generic.py`
  - command-specific filter tests as added
- [x] Add CLI tests:
  - `tests/test_cli_run.py`
- [x] Add regression cases for current tricky planning behavior:
  - env prefixes
  - disabled flags if still kept
  - absolute executable paths
  - redirect suffixes
  - `head`/`tail`
  - compound commands
  - pipes
  - unsupported commands
- [x] Add failure-mode tests:
  - subprocess non-zero exit
  - timeout behavior
  - filter failure fallback

#### Definition of done

- [x] Each architectural layer has direct tests.
- [x] Each PYTK-AI module has dedicated tests.
- [x] Each non-trivial PYTK-AI function has direct or indirect behavioral coverage.
- [x] Coverage target is effectively 100% for PYTK-AI-owned logic.
- [x] CLI tests cover only CLI contract, not planner internals.

### Phase 9 — packaging and developer ergonomics

#### Goal

Make PYTK-AI easy to ship and maintain.

#### Tasks

- [x] Verify package data inclusion for `src/pytk_ai/data/rules.json`.
- [x] Verify entrypoint exposes `pytk-ai`.
- [x] Ensure imports are safe without optional runtime dependencies.
- [x] Run compile check for `src` and `tests`.
- [x] Run full unittest suite.
- [x] Update top-level docs/examples to use `pytk-ai run` and `run_command`.
- [x] Remove stale references to public rewrite-first behavior.

#### Definition of done

- [x] PYTK-AI is packageable as a small pure-Python project.
- [x] Docs match shipped behavior.

## Parallel work packets

### Packet A — planning models and rules

- [x] Files:
  - `src/pytk_ai/plan/models.py`
  - `src/pytk_ai/plan/rules.py`
  - `src/pytk_ai/data/rules.json`
- [x] Do not edit:
  - `src/pytk_ai/plan/scanner.py`
  - `src/pytk_ai/plan/normalize.py`
  - `src/pytk_ai/runner.py`

### Packet B — normalization helpers

- [x] Files:
  - `src/pytk_ai/plan/normalize.py`
- [x] Do not edit:
  - rules loader contracts
  - runner/CLI

### Packet C — compound scanner

- [x] Files:
  - `src/pytk_ai/plan/scanner.py`
- [x] Do not edit:
  - normalize helper signatures
  - runner/CLI

### Packet D — planner orchestration

- [x] Files:
  - `src/pytk_ai/plan/planner.py`
  - `src/pytk_ai/plan/__init__.py`
- [x] Depends on:
  - packet A
  - packet B
  - packet C

### Packet E — result models and runner

- [x] Files:
  - `src/pytk_ai/models.py`
  - `src/pytk_ai/subprocess_utils.py`
  - `src/pytk_ai/runner.py`
- [x] Depends on:
  - packet D interface availability

### Packet F — filters

- [x] Files:
  - `src/pytk_ai/filters/*`
- [x] Depends on:
  - packet E result contracts

### Packet G — CLI simplification

- [x] Files:
  - `src/pytk_ai/cli.py`
  - `src/pytk_ai/__main__.py`
- [x] Depends on:
  - packet E
  - packet F minimum generic filter

### Packet H — tests

- [x] Files:
  - `tests/*`
- [x] Rule: create/expand tests alongside each implementation packet instead of deferring all coverage to the end.
- [x] Can run in parallel by layer after interfaces are frozen.

## Recommended execution order

- [x] 1. Phase 0 decisions
- [x] 2. Packet A
- [x] 3. Packet B + Packet C in parallel
- [x] 4. Packet D
- [x] 5. Packet E
- [x] 6. Packet F
- [x] 7. Packet G
- [x] 8. Packet H continuously, finalize at end
- [x] 9. Packaging/docs cleanup

## Completion checklist

- [x] `pytk-ai run` is the public CLI entrypoint.
- [x] `run_command` is the public library entrypoint.
- [x] planning/rewrite is internal-only.
- [x] no compatibility scaffolding remains just to mirror Rust.
- [x] tests cover planner, runner, filters, and CLI.
- [x] tests systematically cover each PYTK-AI module and non-trivial function.
- [x] coverage target is met for PYTK-AI-owned logic without wasting tests on system/signature guarantees.
- [x] docs and package metadata match actual PYTK-AI behavior.