# PLAN

## Frozen project decisions

- PTK is a new Python project, not a compatibility layer for the Rust tree.
- `rtk/` is reference-only.
- No backward-compatibility work is required for the legacy Rust library or CLI shape.
- Public CLI surface should converge on `ptk run <command>`.
- Command rewrite/planning remains internal implementation detail.
- Public Python API should converge on execute-and-strip entrypoints, not public rewrite entrypoints.
- Testing is systematic at function and module level, with a target of 100% coverage for PTK-owned logic.
- Tests should not restate guarantees already provided by Python, the standard library, or a function signature; they should focus on PTK behavior, branching, contracts, and failure modes.

## Target end state

### Public surfaces

- CLI:
  - `ptk run <command>`
- Library:
  - `from ptk.runner import run_command`
- Optional lower-level internal APIs:
  - `ptk.plan.plan_command`
  - `ptk.filters.filter_output`
  - `ptk.subprocess_utils.execute_raw`

### Internal package map

- `src/ptk/__init__.py`
- `src/ptk/__main__.py`
- `src/ptk/cli.py`
- `src/ptk/models.py`
- `src/ptk/config.py`
- `src/ptk/runner.py`
- `src/ptk/subprocess_utils.py`
- `src/ptk/plan/__init__.py`
- `src/ptk/plan/models.py`
- `src/ptk/plan/scanner.py`
- `src/ptk/plan/normalize.py`
- `src/ptk/plan/rules.py`
- `src/ptk/plan/planner.py`
- `src/ptk/filters/__init__.py`
- `src/ptk/filters/base.py`
- `src/ptk/filters/generic.py`
- `src/ptk/filters/system.py`
- `src/ptk/filters/git.py`
- `src/ptk/filters/python.py`
- `src/ptk/data/__init__.py`
- `src/ptk/data/rules.json`

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

- [x] Confirm `ARCHITECTURE.md` remains aligned with the simplified direction: rewrite internal, `ptk run` public, library-first execute-and-strip flow.
- [x] Remove the assumption that `ptk rewrite` must remain public.
- [x] Remove the assumption that `src/ptk/rewrite.py` must remain a compatibility facade.
- [x] Record in docs and task notes that Rust behavior is reference input, not a compatibility contract.
- [x] Define the current migration target as “build the Python architecture cleanly from scratch while reusing only useful logic”.

### Phase 1 — decompose the current code into architecture-ready modules

#### Goal

Split the current `src/ptk/rewrite.py` logic into pure planning modules that can be tested and evolved independently.

#### Tasks

- [ ] Inventory the current responsibilities in `src/ptk/rewrite.py`:
  - rule loading
  - env-prefix handling
  - redirect stripping/preservation
  - absolute-path normalization
  - rule matching
  - `head`/`tail` rewrite logic
  - compound command scanning
  - segment orchestration
  - public rewrite result shape
- [ ] Create `src/ptk/plan/` package.
- [ ] Move planning dataclasses into `src/ptk/plan/models.py`.
- [ ] Move rule loading/compilation into `src/ptk/plan/rules.py`.
- [ ] Move normalization helpers into `src/ptk/plan/normalize.py`.
- [ ] Move compound command scanning into `src/ptk/plan/scanner.py`.
- [ ] Move segment rewrite orchestration into `src/ptk/plan/planner.py`.
- [ ] Replace direct `rewrite_*` naming in the internal architecture with planning-oriented names where useful.
- [ ] Keep planning pure: no subprocess calls, no filtering, no CLI printing.
- [ ] Decide whether `src/ptk/rewrite.py` is deleted outright or replaced temporarily during transition.
- [ ] Add `src/ptk/plan/__init__.py` exports only for internal planning primitives actually needed elsewhere.

#### Definition of done

- [ ] No single planning file owns unrelated concerns.
- [ ] Rule loading exists in one place only.
- [ ] Planner imports flow one direction: models/data -> helpers -> planner.
- [ ] Planning modules are testable without subprocesses.

### Phase 2 — define stable result and configuration models

#### Goal

Create the structured contracts needed by the future runner and CLI.

#### Tasks

- [ ] Add `src/ptk/models.py`.
- [ ] Define `ExecutionResult` with raw stdout/stderr/exit code/executed command.
- [ ] Define `FilterResult` with filtered output/filter name/error metadata.
- [ ] Define `CommandResult` with original command, executed command, rewritten/planned flags, raw outputs, filtered output, exit code, and error field.
- [ ] Define minimal option/config structures needed by `run_command`.
- [ ] Keep models serialization-safe and CLI-friendly.
- [ ] Decide whether plan-layer models stay in `ptk.plan.models` and run-layer models stay in `ptk.models`.

#### Definition of done

- [ ] Runner and CLI can share the same result object.
- [ ] No caller needs to parse CLI text to consume PTK output.

### Phase 3 — build the internal planning API

#### Goal

Expose an internal `plan_command` flow that transforms raw command text into a reusable command plan.

#### Tasks

- [ ] Define `CommandPlan` fields.
- [ ] Decide whether plan output stores:
  - original command
  - normalized command
  - planned command to execute
  - whether PTK-managed path was selected
  - matched rule/filter hints
  - skip reason when unsupported
- [ ] Implement `plan_command(command, excluded=None)` in `src/ptk/plan/planner.py`.
- [ ] Preserve current high-value rewrite behavior where still relevant to the internal planner.
- [ ] Preserve shell-sensitive cases already handled well: quoting, compound ops, redirect suffixes, env prefixes.
- [ ] Add explicit skip reasons instead of silent `None` where it helps debugging and tests.
- [ ] Ensure planner can express both “PTK-managed execution path” and “raw shell fallback”.
- [ ] Ensure planner can later carry filter hints without re-parsing command text downstream.

#### Definition of done

- [ ] Planner is the single source of truth for command normalization/selection.
- [ ] Runner can consume planner output directly.

### Phase 4 — build subprocess execution layer

#### Goal

Separate command execution from planning and filtering.

#### Tasks

- [ ] Add `src/ptk/subprocess_utils.py`.
- [ ] Implement `execute_raw(...)` helper with cwd/env/timeout support.
- [ ] Decide exact subprocess invocation strategy for planned PTK-managed commands versus raw shell fallback.
- [ ] Capture stdout, stderr, exit code, and executed command.
- [ ] Preserve underlying exit code.
- [ ] Make timeout and execution failures explicit in result objects.
- [ ] Keep execution layer independent from filter selection logic.

#### Definition of done

- [ ] Raw execution can be tested separately from planner and filters.
- [ ] Execution errors do not corrupt stdout/stderr capture contracts.

### Phase 5 — build filtering layer

#### Goal

Return compact useful output after execution.

#### Tasks

- [ ] Add `src/ptk/filters/` package.
- [ ] Add `src/ptk/filters/base.py` for shared filter interfaces/helpers.
- [ ] Add `src/ptk/filters/generic.py` with a small generic fallback:
  - ANSI stripping
  - repeated-line collapse
  - progress/noise reduction
  - output truncation policy
- [ ] Decide generic stderr policy for success vs failure cases.
- [ ] Add command-specific filter modules incrementally:
  - `src/ptk/filters/system.py`
  - `src/ptk/filters/git.py`
  - `src/ptk/filters/python.py`
- [ ] Define filter selection strategy from plan hints first, command matching second.
- [ ] Ensure filter failure falls back to raw output safely.

#### Definition of done

- [ ] Generic fallback works even when no command-specific filter exists.
- [ ] Filtering cannot hide the underlying exit code.

### Phase 6 — build `run_command`

#### Goal

Implement the main public library entrypoint.

#### Tasks

- [ ] Add `src/ptk/runner.py`.
- [ ] Implement `run_command(command, *, cwd=None, env=None, timeout=None, rewrite=True)` or rename the flag to something architecture-consistent like `plan=True`.
- [ ] Runner flow must be:
  1. call planner
  2. choose PTK-managed or raw execution path
  3. execute
  4. filter
  5. return `CommandResult`
- [ ] Ensure runner preserves original command and actual executed command.
- [ ] Ensure raw output remains available even if filtering fails.
- [ ] Ensure runner returns structured errors rather than raising for normal command failures.

#### Definition of done

- [ ] `run_command` is the primary stable library interface.
- [ ] CLI can delegate almost entirely to runner.

### Phase 7 — simplify the CLI to `ptk run`

#### Goal

Make CLI a thin wrapper around the library.

#### Tasks

- [ ] Refactor `src/ptk/cli.py` around `ptk run`.
- [ ] Remove public `rewrite` subcommand.
- [ ] Decide whether hook support stays now or moves behind internal/secondary subcommands later.
- [ ] Ensure `ptk run <command>` joins command args safely and sends them to `run_command`.
- [ ] Print filtered output by default.
- [ ] Exit with underlying command exit code.
- [ ] Keep CLI argument parsing thin; do not re-implement planning or filtering in CLI.

#### Definition of done

- [ ] The CLI is a small adapter over the library.
- [ ] Public CLI behavior matches the architecture doc.

### Phase 8 — tests and regression coverage

#### Goal

Restructure tests around the new architecture and keep each work area isolated.

#### Tasks

- [ ] Treat test creation as required work for every new module and every non-trivial function.
- [ ] Aim for 100% coverage across PTK-owned logic.
- [ ] Do not add tests that only re-verify Python/runtime/stdlib guarantees or obvious type-signature behavior; spend coverage budget on PTK-specific logic, branches, contracts, and failure modes.
- [ ] Replace `tests/test_rewrite.py` with architecture-aligned tests.
- [ ] Add planning-focused tests:
  - `tests/test_plan_rules.py`
  - `tests/test_plan_normalize.py`
  - `tests/test_plan_scanner.py`
  - `tests/test_plan_planner.py`
- [ ] Add runner tests:
  - `tests/test_runner.py`
- [ ] Add filter tests:
  - `tests/test_filters_generic.py`
  - command-specific filter tests as added
- [ ] Add CLI tests:
  - `tests/test_cli_run.py`
- [ ] Add regression cases for current tricky planning behavior:
  - env prefixes
  - disabled flags if still kept
  - absolute executable paths
  - redirect suffixes
  - `head`/`tail`
  - compound commands
  - pipes
  - unsupported commands
- [ ] Add failure-mode tests:
  - subprocess non-zero exit
  - timeout behavior
  - filter failure fallback

#### Definition of done

- [ ] Each architectural layer has direct tests.
- [ ] Each PTK module has dedicated tests.
- [ ] Each non-trivial PTK function has direct or indirect behavioral coverage.
- [ ] Coverage target is effectively 100% for PTK-owned logic.
- [ ] CLI tests cover only CLI contract, not planner internals.

### Phase 9 — packaging and developer ergonomics

#### Goal

Make PTK easy to ship and maintain.

#### Tasks

- [ ] Verify package data inclusion for `src/ptk/data/rules.json`.
- [ ] Verify entrypoint exposes `ptk`.
- [ ] Ensure imports are safe without optional runtime dependencies.
- [ ] Run compile check for `src` and `tests`.
- [ ] Run full unittest suite.
- [ ] Update top-level docs/examples to use `ptk run` and `run_command`.
- [ ] Remove stale references to public rewrite-first behavior.

#### Definition of done

- [ ] PTK is packageable as a small pure-Python project.
- [ ] Docs match shipped behavior.

## Parallel work packets

### Packet A — planning models and rules

- [ ] Files:
  - `src/ptk/plan/models.py`
  - `src/ptk/plan/rules.py`
  - `src/ptk/data/rules.json`
- [ ] Do not edit:
  - `src/ptk/plan/scanner.py`
  - `src/ptk/plan/normalize.py`
  - `src/ptk/runner.py`

### Packet B — normalization helpers

- [ ] Files:
  - `src/ptk/plan/normalize.py`
- [ ] Do not edit:
  - rules loader contracts
  - runner/CLI

### Packet C — compound scanner

- [ ] Files:
  - `src/ptk/plan/scanner.py`
- [ ] Do not edit:
  - normalize helper signatures
  - runner/CLI

### Packet D — planner orchestration

- [ ] Files:
  - `src/ptk/plan/planner.py`
  - `src/ptk/plan/__init__.py`
- [ ] Depends on:
  - packet A
  - packet B
  - packet C

### Packet E — result models and runner

- [ ] Files:
  - `src/ptk/models.py`
  - `src/ptk/subprocess_utils.py`
  - `src/ptk/runner.py`
- [ ] Depends on:
  - packet D interface availability

### Packet F — filters

- [ ] Files:
  - `src/ptk/filters/*`
- [ ] Depends on:
  - packet E result contracts

### Packet G — CLI simplification

- [ ] Files:
  - `src/ptk/cli.py`
  - `src/ptk/__main__.py`
- [ ] Depends on:
  - packet E
  - packet F minimum generic filter

### Packet H — tests

- [ ] Files:
  - `tests/*`
- [ ] Rule: create/expand tests alongside each implementation packet instead of deferring all coverage to the end.
- [ ] Can run in parallel by layer after interfaces are frozen.

## Recommended execution order

- [x] 1. Phase 0 decisions
- [ ] 2. Packet A
- [ ] 3. Packet B + Packet C in parallel
- [ ] 4. Packet D
- [ ] 5. Packet E
- [ ] 6. Packet F
- [ ] 7. Packet G
- [ ] 8. Packet H continuously, finalize at end
- [ ] 9. Packaging/docs cleanup

## Completion checklist

- [ ] `ptk run` is the public CLI entrypoint.
- [ ] `run_command` is the public library entrypoint.
- [ ] planning/rewrite is internal-only.
- [ ] no compatibility scaffolding remains just to mirror Rust.
- [ ] tests cover planner, runner, filters, and CLI.
- [ ] tests systematically cover each PTK module and non-trivial function.
- [ ] coverage target is met for PTK-owned logic without wasting tests on system/signature guarantees.
- [ ] docs and package metadata match actual PTK behavior.