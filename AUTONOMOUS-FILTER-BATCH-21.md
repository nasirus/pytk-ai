# Autonomous Filter Batch 21

## Scope

Work only on the final narrowed `CORE-01` closure step:

- package PTK-owned built-in TOML fallback filter data
- remove the runtime dependency on the checked-out `rtk/src/filters/*.toml` tree

## Source Of Truth

- `FILTERS-LIST-RTK.md`
- `rtk/src/core/toml_filter.rs`
- `rtk/src/filters/*.toml`
- `FILTERS-REVIEW-WORKBOARD.md`

## Important Current Context

- The user explicitly narrowed `CORE-01` scope to only these two goals:
  - cover commands not worth a full custom module
  - support declarative data-driven built-in filters for long-tail commands
- The user explicitly does **not** want project-local or user-global custom TOML filter support in scope.
- PTK already has a bounded built-in TOML fallback engine and audited stage ordering.
- The remaining blocker to closing `CORE-01` cleanly is that PTK still loads built-in TOML definitions from the checked-out `rtk/src/filters/*.toml` tree at runtime.

## PTK Areas

- `src/pytk_ai/filters/toml_fallback.py`
- a packaged PTK-owned data location under `src/pytk_ai/`
- matching tests under `tests/`
- `FILTERS-REVIEW-WORKBOARD.md`
- `TODO.md`

## Required Outcome

- Vendor/package PTK-owned built-in TOML filter data into the PTK package.
- Update PTK fallback loading to use packaged PTK-owned data, not the live `rtk/` checkout.
- Keep project-local and user-global custom TOML loading explicitly out of scope.
- If this cleanly satisfies the narrowed `CORE-01` scope, close `CORE-01` in the workboard and fix queue.

## Focus Update Requirement

- In your final report back to the controller, include a concise focus update with all necessary context:
  - exact packaged data location chosen
  - exact runtime dependency removed
  - exact tests added/updated
  - whether `CORE-01` is now honestly closable under the narrowed scope
  - exact row/fix-queue status changes made
  - any residual out-of-scope items that remain intentionally excluded

## Constraints

- Keep changes scoped to the narrowed `CORE-01` closure step only.
- Do not add project-local `.rtk/filters.toml` loading.
- Do not add user-global config loading.
- Do not create commits.

## Validation

- `python3 -m unittest` for targeted touched tests
- `uv run ruff format && uv run ruff check`

## Report Back

Return only:

- focus update
- changed files
- target rows fixed
- target rows partially improved
- target rows still open
- tests run and results
- blockers or follow-up work
