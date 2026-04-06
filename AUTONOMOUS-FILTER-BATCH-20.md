# Autonomous Filter Batch 20

## Scope

Work only on this small TOML-backed system utility batch:

- `TOML-SYS-01` `df.toml`
- `TOML-SYS-02` `du.toml`
- `TOML-SYS-07` `ping.toml`
- `TOML-SYS-08` `ps.toml`

## Source Of Truth

- `FILTERS-LIST-RTK.md`
- `rtk/src/filters/df.toml`
- `rtk/src/filters/du.toml`
- `rtk/src/filters/ping.toml`
- `rtk/src/filters/ps.toml`
- `FILTERS-REVIEW-WORKBOARD.md`

## Important Current Context

- PTK now has a bounded built-in TOML fallback engine on the generic path via `src/pytk_ai/filters/toml_fallback.py`.
- These rows are still marked missing in the workboard, so this batch must verify whether that is now stale.
- If the new bounded fallback engine materially closes these specific built-in rows, update them honestly instead of adding unnecessary new wrapper/filter code.

## PTK Areas

- `src/pytk_ai/filters/toml_fallback.py`
- `src/pytk_ai/filters/generic.py`
- `tests/test_filters_generic.py`
- `FILTERS-REVIEW-WORKBOARD.md`
- `TODO.md`

## Required Outcome

- Re-audit these four TOML rows against the new PTK fallback behavior.
- If PTK already materially covers them, add/adjust targeted regression tests and update row statuses/workboard notes.
- If any specific row is still missing, make the smallest correct fix and document it.

## Focus Update Requirement

- In your final report back to the controller, include a concise focus update with all necessary context:
  - whether each of the four rows was stale vs truly missing
  - exact files changed
  - exact tests added/updated
  - exact row status changes made
  - any residual gap left for these rows

## Constraints

- Keep changes scoped to these four TOML system rows only.
- Do not broaden the TOML engine beyond what is needed for this batch.
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
