# Add Filter Plan

This file tracks missing PYTK-AI filter work that should be handled in later sessions.

Scope:
- Focus on filters that produce meaningful token savings in agent harnesses.
- Prefer commands that are noisy, common, and safe to summarize.
- Keep implementation incremental and reviewable.
- Use the legacy Rust RTK repository at `/rtk` as the reference implementation source when reimplementing filters in Python.
- Keep filter modules separated inside `src/pytk_ai/filters/`; do not accumulate unrelated filter logic in a single file.

Current Python filter coverage:
- `ls`
- `find`
- `grep` / `rg`
- `git` (light cleanup only)
- `pytest`
- `ruff`
- `mypy`
- generic fallback

Priority rules:
1. Ship filters that remove the most noise from common agent workflows first.
2. Prefer failure-oriented summaries for test/build/lint commands.
3. Preserve raw output on command failure when summarization would hide needed detail.
4. Add regression tests for each filter before marking it done.

Reference implementation workflow:
1. Before adding a new Python filter, inspect the corresponding implementation in `/rtk`.
2. Read the command docs first in `/rtk/README.md`, `/rtk/docs/FEATURES.md`, and any command-specific README files.
3. Then inspect the actual Rust implementation under `/rtk/src/`.
4. If the Rust filter is TOML-driven, also inspect `/rtk/src/filters/` and `/rtk/docs/filter-workflow.md`.
5. Reimplement the behavior in Python only after identifying the real compression strategy:
   - noise removal
   - grouping
   - truncation
   - deduplication
   - failure-only summarization
6. Do not copy legacy behavior blindly when it depends on Rust-only infrastructure or broader RTK features that do not exist in PYTK-AI yet.
7. When a Python filter intentionally diverges from `/rtk`, document the reason in the code or tests.

Filter module structure rules:
1. Keep each filter family in its own module under `src/pytk_ai/filters/`.
2. Extend `src/pytk_ai/filters/__init__.py` only to register and dispatch filters.
3. Put shared cleanup helpers in `src/pytk_ai/filters/base.py` only when they are genuinely reusable.
4. Do not mix unrelated command families into `generic.py`.
5. If a filter grows sub-modes with substantial logic, split it further instead of creating one oversized module.
6. Mirror the task structure in tests so each filter module has focused regression coverage.

## Phase 1: High-value filters

- [x] `git diff`
  - Goal: compact diff/stat summary, file counts, trimmed patch context.
  - Why: common in agent review loops and usually very token-heavy.

- [x] `git show`
  - Goal: compact commit summary plus bounded diff/stat output.
  - Why: frequent inspection command with large raw output.

- [x] `git log`
  - Goal: normalize to one-line commit summaries with configurable limits.
  - Why: common and cheap to compress.

- [x] `git branch`
  - Goal: compact branch listing, highlight current branch, trim remote noise.
  - Why: common status command in repos with many branches.

- [x] `git add`
  - Goal: reduce successful output to minimal acknowledgment.
  - Why: command result is usually low-information.

- [x] `git commit`
  - Goal: keep commit hash and essential summary only.
  - Why: success output is verbose relative to value.

- [x] `git push`
  - Goal: keep destination, branch, and status summary; drop boilerplate.
  - Why: strong savings for common agent workflows.

- [x] `git pull`
  - Goal: summarize changed files and insertions/deletions.
  - Why: frequent and often noisy.

- [x] `git fetch`
  - Goal: keep branch/tag update summary only.
  - Why: remote update output is repetitive.

- [x] `git stash`
  - Goal: compact stash action/result summary.
  - Why: low-information success output.

- [x] `git worktree`
  - Goal: concise worktree list/status format.
  - Why: useful in multi-worktree agent setups.

- [x] `cargo test`
  - Goal: failures/errors summary, final totals, no passing test spam.
  - Why: one of the highest-value agent commands.

- [x] generic `test` command wrapper
  - Goal: recognize `npm test`, `pnpm test`, `yarn test`, `make test`, etc.
  - Why: large savings if failures-only summaries are applied consistently.

- [x] `ruff check`
  - Goal: compact violations grouped by file/rule.
  - Why: current Python port only labels it; it does not summarize findings.

- [x] `cat`
  - Goal: bounded file reading with line windows, optional aggressive summarization.
  - Why: high-frequency agent command with large token risk.

- [x] `head`
  - Goal: normalize line-range reads and suppress redundant noise.
  - Why: very common in shell-based file inspection.

- [x] `tail`
  - Goal: normalize tail output and deduplicate repetitive log lines.
  - Why: useful for logs and recent file content.

## Phase 2: Build and lint filters

- [x] `cargo build`
- [x] `cargo clippy`
- [x] `cargo fmt --check`
- [x] `mypy`
  - Improve from current minimal handling to grouped diagnostics.
- [x] `pytest`
  - Improve from current summary extraction to richer failure grouping.
- [x] `eslint`
- [x] `biome`
- [x] `tsc`
- [x] `next build`
- [x] `go test`
- [x] `golangci-lint run`
- [x] `rubocop`
- [x] `rspec`

## Phase 3: File and search filters

- [x] `tree`
- [x] `wc`
- [x] `diff`
- [x] `read`
  - Add command-specific behavior rather than using the current system fallback.
- [x] `rg`
  - Add grouped/multi-file search summaries beyond plain passthrough.

## Phase 4: Package manager filters

- [x] `pip list`
- [x] `pip outdated`
- [x] `uv sync`
- [x] `pnpm list`
- [x] `npm list`
- [x] `bundle install`
- [x] `prisma generate`

## Phase 5: Container and infra filters

- [x] `docker ps`
- [x] `docker images`
- [x] `docker logs`
- [x] `docker compose ps`
- [x] `kubectl pods`
- [x] `kubectl services`
- [x] `kubectl logs`
- [x] `aws` high-volume read commands
- [x] `terraform plan`
- [x] `terraform validate`

## Phase 6: GitHub and API-oriented filters

- [x] `gh pr list`
- [x] `gh pr view`
- [x] `gh issue list`
- [x] `gh run list`
- [x] `curl` for JSON/schema summarization
- [x] `wget` progress/output cleanup

## Cross-cutting tasks

- [ ] Expand planner rules so new filters are discoverable and selected correctly.
- [ ] Add per-filter regression tests in `tests/`.
- [ ] Add failure-mode tests to ensure raw output is preserved when needed.
- [ ] Add benchmark scenarios for each high-value filter family.
- [ ] Record token-savings evidence before and after each filter lands.
- [ ] Define when a filter should summarize success only, failure only, or both.
- [ ] Decide whether filter behavior should differ for interactive vs hook use.
- [ ] Add structured metrics support for filter benchmarking and future `gain`-style analytics.

## Suggested implementation order

1. `git diff`, `git show`, `git log`
2. `cargo test`, `ruff check`, improved `pytest`
3. `cat`, `head`, `tail`, improved `rg`
4. `git push`, `git pull`, `git branch`
5. `eslint`, `tsc`, `cargo build`
6. `docker ps`, `docker logs`, `kubectl logs`

## Done criteria for each filter

- [ ] Planner recognizes the command correctly.
- [ ] Output is materially smaller on realistic noisy examples.
- [ ] Success and failure behavior are both tested.
- [ ] Filter preserves actionable information for agent decision-making.
- [ ] Benchmark evidence is captured in `labs/compare_bash_and_pytk_ai.py` or a dedicated benchmark.
