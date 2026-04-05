# PTK Architecture

## Goal

PTK is a Python package and CLI that accepts a bash command as text, executes it, and returns a stripped, token-efficient result.

## Migration status

Current repository status:

- the current Python scaffold still contains rewrite-first pieces such as `src/ptk/rewrite.py` and the temporary `ptk rewrite` CLI path
- those pieces are transition scaffolding, not the target public contract
- the target public CLI is `ptk run <command>`
- the target public library entrypoint is `from ptk.runner import run_command`
- command rewrite/planning remains internal implementation detail behind execution
- the Rust tree in `rtk/` is reference material for useful logic only, not a compatibility contract for PTK behavior, module layout, or CLI shape
- `src/ptk/rewrite.py` is the current implementation host for planning logic, but it is not required to survive as a permanent compatibility facade; Phase 1 may split or remove it as the new `ptk.plan` package lands

This migration target is: build the Python architecture cleanly from scratch while reusing only useful logic.

It must work in two modes:

1. **CLI**
   - `ptk run "git status"`

2. **Library**
   - importable from Python scripts
   - callable as full execute-and-strip logic

PTK keeps the public name `ptk` and is designed to be installable from PyPI with minimal runtime dependencies.

---

## Scope

### In scope

- command rewriting
- command execution
- output stripping and summarization
- reusable Python API
- small CLI wrapper
- testable, dependency-light packaging

### Out of scope for the first phase

- hook installers and agent-specific hook management
- analytics dashboards
- large installation flows
- Rust parity for every RTK feature before the Python core is stable

---

## Product surfaces

### 1. Python library

Primary use:

```python
from ptk.runner import run_command
```

Target usage:

```python
result = run_command("git status")
print(result.filtered_output)
print(result.exit_code)
```

The library should expose stable functions and structured result objects.

### 2. CLI

Primary commands:

- `ptk run <command>`

The CLI should stay thin and delegate to the library.

---

## High-level execution flow

```text
input command string
        |
        v
plan / normalize
        |
        v
execution plan
        |
        v
run subprocess
        |
        v
capture stdout/stderr/exit code
        |
        v
apply command-specific or generic filter
        |
        v
return structured result
        |
        +--> CLI prints filtered output
        +--> Python caller consumes result object
```

---

## Core components

## 1. Command planning engine

Purpose:
- accept raw shell command text
- detect whether PTK has a specialized execution/filter path
- normalize supported commands into an internal execution plan
- preserve shell semantics where possible

Responsibilities:
- shell-aware tokenization
- compound command handling (`&&`, `||`, `;`, `|`, `&`)
- env-prefix preservation (`FOO=1 git status`)
- redirect preservation (`2>&1`, `>/tmp/x`)
- special-case normalization like `head`/`tail` to PTK read-style handling
- skip rules for unsafe or incompatible cases

Design rule:
- planning logic should be **pure** and testable without executing subprocesses

Suggested module area:
- `ptk.plan`
- `ptk.lexer`
- `ptk.rules`

Note:
- PTK does not need a public `ptk rewrite` command.
- The planning/rewrite step is an internal implementation detail behind `ptk run`.

---

## 2. Command execution engine

Purpose:
- accept a command string
- decide whether to execute raw command or PTK-managed command path
- run the subprocess
- capture outputs and exit code

Responsibilities:
- subprocess invocation
- stdout/stderr capture
- exit-code preservation
- optional timeout and cwd/env support
- safe fallback when PTK-specific filtering fails

Design rule:
- execution and filtering must be separate layers
- if filtering fails, callers should still be able to recover raw output

Suggested module area:
- `ptk.runner`
- `ptk.subprocess_utils`

---

## 3. Filter layer

Purpose:
- strip noisy output after command execution
- return the smallest useful representation for LLM or script consumption

Two filter types:

### A. Command-specific filters

Used for high-value commands such as:
- `git status`
- `git diff`
- `git log`
- `pytest`
- `ls`
- `grep`
- `read`

These can use custom parsing logic and structured summarization.

### B. Generic filters

Used when no command-specific filter exists.

Examples:
- strip ANSI
- drop progress bars
- collapse repeated lines
- keep stderr only on failure
- line truncation / head / tail

Design rule:
- start with a small generic fallback
- add command-specific filters incrementally for the biggest wins

Suggested module area:
- `ptk.filters.base`
- `ptk.filters.system`
- `ptk.filters.git`
- `ptk.filters.python`

---

## 4. Result model

Purpose:
- give both CLI and Python callers a consistent structured output contract

Suggested result shape:

```text
CommandResult
  - command: original input command
  - executed_command: actual subprocess command
  - rewritten: bool
  - stdout: raw stdout
  - stderr: raw stderr
  - filtered_output: stripped result
  - exit_code: int
  - filter_name: str | None
  - error: str | None
```

Design rule:
- never force callers to parse CLI text when they import the library
- the CLI should simply print fields from the same result object

Suggested module area:
- `ptk.models`

---

## 5. Rules and data

Purpose:
- keep command-planning rules and filter metadata in a reusable data layer

Responsibilities:
- static command-planning rule registry
- prefix replacement metadata
- command categories
- future filter capability metadata

Design rule:
- keep planning rules data-driven where practical
- avoid scattering command-prefix knowledge across many files

Suggested module area:
- `ptk.data/`
- `ptk.rules`

---

## 6. Configuration

Purpose:
- allow callers and users to control behavior without changing code

Likely settings:
- excluded commands
- max output lines
- timeout
- cwd
- env overrides
- filtering level
- raw-output fallback behavior

Design rule:
- Python API should accept explicit arguments first
- config files are secondary, not required for normal use

Suggested module area:
- `ptk.config`

---

## Public API direction

## Full execution API

```python
run_command(
    command: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    rewrite: bool = True,
) -> CommandResult
```

Use when the caller wants PTK to execute the command and return stripped output.

## Internal planning API

```python
plan_command(command: str, excluded: Sequence[str] | None = None) -> CommandPlan
```

Use internally to keep parsing and execution separated, without exposing rewrite as a public product feature.

## Lower-level execution API

```python
execute_raw(command: str, ...) -> ExecutionResult
filter_output(command: str, stdout: str, stderr: str, exit_code: int) -> FilterResult
```

Use when callers want only part of the pipeline.

---

## CLI direction

### `ptk run`

- input: raw command string
- behavior: plan internal execution path, execute, filter, print stripped output
- exit with the underlying command exit code

This keeps CLI behavior aligned with library behavior.

---

## Packaging direction

PTK should remain:

- pure Python
- small install footprint
- standard-library-first where possible
- installable with `pip install ptk`

Implications:

- avoid framework-heavy architecture
- keep modules import-safe
- separate pure logic from subprocess side effects
- keep data files package-included

---

## Phased implementation plan

### Phase 0 — public-direction reset

- keep `ptk run` and `run_command` as the migration target public surfaces
- treat rewrite/planning as internal-only architecture
- treat `rtk/` as reference input, not a compatibility requirement
- allow current rewrite-first modules to be transitional and removable

### Phase 1 — Rewrite core

- finalize command planning parity for supported commands
- stabilize internal planning API for `plan_command`
- keep CLI thin

### Phase 2 — Generic execute-and-strip pipeline

- add `run_command`
- add structured result models
- add generic filtering fallback
- preserve exit codes and raw outputs

### Phase 3 — High-value command filters

- system: `read`, `ls`, `grep`
- git: `status`, `log`, `diff`
- python: `pytest`

### Phase 4 — Optional advanced features

- config files
- tracking / metrics
- declarative filter registry

---

## Architectural principles

1. **Library first**
   - CLI is a wrapper around importable Python functions.

2. **Pure planning core**
   - command planning must be testable without subprocesses.

3. **Fail safe**
   - if filtering breaks, raw command output must still be recoverable.

4. **Exit-code fidelity**
   - PTK must preserve the underlying command exit code.

5. **Small surface area**
   - start with a compact, maintainable core before broad command coverage.

6. **Single source of truth**
   - planning rules and command mappings should live in one canonical place.

7. **Incremental command support**
   - add command-specific filters only where they materially improve token reduction.

---

## Summary

PTK should become a small Python command-processing engine with two faces:

- a **library** that can rewrite, execute, and strip bash command output
- a **CLI** that exposes the same behavior for shell workflows

The first stable core is:

1. parse and plan command text
2. execute command safely
3. strip output with generic or command-specific filters
4. return a structured result object

Everything else is secondary.