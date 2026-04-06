# RTK to PTK Filter Review Workboard

This document is the shared workboard for a full RTK-to-PTK filter review.

`FILTERS-LIST-RTK.md` is the golden truth for review scope.

It is designed for multiple specialized agents to use collaboratively:

- pick one review unit at a time
- verify whether PTK has a command-aware counterpart
- compare Rust and Python behavior in detail
- record discrepancies and fix candidates
- update status without rewriting unrelated rows

## Scope

- Golden truth: `FILTERS-LIST-RTK.md`
- PTK inventory source: `FILTERS-LIST-PTK.md`
- Verified code anchors used for initial mapping:
  - `rtk/src/main.rs`
  - `rtk/src/core/toml_filter.rs`
  - `src/pytk_ai/plan/normalize.py`
  - `src/pytk_ai/filters/*.py`

## Source Of Truth Rule

- Review scope starts from RTK, never from PTK.
- Every RTK filter or RTK filter family listed in `FILTERS-LIST-RTK.md` must have exactly one review unit in this workboard.
- If PTK behavior, PTK inventory, or code comments disagree with the RTK inventory, treat RTK as correct until proven otherwise.
- PTK-only filters are out of scope unless they affect conformance for an RTK review unit.
- When a row is updated, confirm the RTK source entry first, then compare PTK.

## Working Rules

- One row equals one review unit.
- Rows are derived from the RTK inventory, not from PTK implementation shape.
- `PTK Coverage` means command-aware PTK behavior, not the generic fallback filter.
- If PTK only has a broader or different filter, mark `Partial` until behavior is proven equivalent.
- If PTK has no command-aware counterpart, mark `No` and treat it as a gap.
- Do not replace prior findings. Append new findings to `## Findings Log` and update the row status.
- When a fix is identified but not yet implemented, add it to `## Fix Queue`.

## Status Legend

| Field | Values | Meaning |
| --- | --- | --- |
| `PTK Coverage` | `Yes`, `Partial`, `No` | Whether PTK has a command-aware counterpart for the RTK review unit |
| `Conformance` | `Not audited`, `Known scope gap`, `Missing in PTK`, `Conforms`, `Discrepant`, `Fixed in PTK` | Current parity state |
| `Work State` | `todo`, `in_review`, `reviewed`, `fix_planned`, `fixed` | Current workflow state |

## Snapshot

- PTK already has direct counterparts for most Git, Python, Go, infra, and file/search filters.
- PTK has partial coverage for RTK read/file filtering levels, some Cargo behaviors, some GH behaviors, Prisma non-generate flows, some package-manager flows, and a small set of TOML overlaps.
- PTK currently lacks RTK's TOML filter engine and many RTK-only command families, especially `gt`, `.NET`, `prettier`, `vitest`, `playwright`, `psql`, `env`, `deps`, `summary`, `json`, `log`, and `local_llm`.

## Recommended Review Order

1. Existing PTK counterparts with likely scope gaps: `CORE-*`, `CARGO-04..07`, `GH-05`, `JS-07..14`, `PY-02`, `CLD-06..07`, `SYS-03`.
2. High-value missing command families: `RUNNER-01`, `RB-01`, `DN-*`, `CLD-13`, `SYS-04`, `SYS-07..10`, `SYS-12`.
3. TOML filters with partial or overlapping PTK support: `TOML-BLD-03`, `TOML-BLD-08`, `TOML-PKG-02`, `TOML-PKG-06`, `TOML-INF-10`.
4. Remaining TOML-only long tail.

## Shared And Core Review Units

| ID | RTK Unit | RTK Source | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CORE-01 | TOML fallback filter pipeline | `rtk/src/core/toml_filter.rs` | `src/pytk_ai/filters/base.py`, `generic.py`, `toml_fallback.py` | Partial | Known scope gap | reviewed | PTK now has a repo-backed built-in-only RTK-style fallback path for generic commands, including command-regex matching and the audited eight-stage transform order, but RTK's packaged built-in registry, project/global filter sources, trust gating, and full registry semantics are still absent. |
| CORE-02 | Raw file read / no filter level | `rtk/src/core/filter.rs`, `rtk/src/cmds/system/read.rs` | `read`, `system.read.*` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai read` surface with RTK-style `--level`, `--max-lines`, `--tail-lines`, stdin (`-`), and optional line-number support instead of only preserving mostly raw `cat`/`head`/`tail` output. |
| CORE-03 | Minimal file filter | `rtk/src/core/filter.rs` | `read`, `src/pytk_ai/filters/files.py` | Yes | Conforms | reviewed | Verified stale row: PTK `pytk-ai read --level minimal` already mirrors the audited RTK slice by stripping language-aware comments, preserving Rust doc comments and Python docstrings, and normalizing blank-line runs. |
| CORE-04 | Aggressive file filter | `rtk/src/core/filter.rs` | `read`, `src/pytk_ai/filters/files.py` | Yes | Conforms | reviewed | Verified stale row: PTK `pytk-ai read --level aggressive` already applies the same reviewed minimal-first reduction, keeping imports, signatures, braces, and key constant/static declarations while eliding implementation bodies. |
| CORE-05 | `smart_truncate()` structural truncation | `rtk/src/core/filter.rs` | generic line caps | Yes | Fixed in PTK | fixed | PTK `read` now uses a structure-aware truncation path that prefers imports, signatures, and boundary lines when applying `--max-lines`, instead of only generic post-cleanup line caps. |

## Programmatic RTK Filters

### Git And VCS

| ID | RTK Unit | RTK Source | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GIT-01 | `git status` | `rtk/src/cmds/git/git.rs` | `git.status` | Yes | Fixed in PTK | fixed | PTK now rewrites bare `git status` execution to porcelain branch mode while preserving user-arg status passthrough, matching the RTK split between compact default status and minimal-filter arg-aware behavior. |
| GIT-02 | `git log` | `rtk/src/cmds/git/git.rs` | `git.log` | Yes | Fixed in PTK | fixed | PTK now injects RTK-style default execution for bare logs with `--pretty`, default limits, and `--no-merges`, and the filter keeps short body lines from the rewritten output. |
| GIT-03 | `git diff` | `rtk/src/cmds/git/git.rs` | `git.diff` | Yes | Fixed in PTK | fixed | PTK now mirrors RTK's default diff wrapper by executing `--stat` first, appending a `--- Changes ---` raw diff section for compaction, and preserving passthrough for stat-only and `--no-compact` modes. |
| GIT-04 | `git show` | `rtk/src/cmds/git/git.rs` | `git.show` | Yes | Fixed in PTK | fixed | PTK now rewrites default `git show` execution into summary plus `--stat` plus diff phases, while preserving passthrough for blob, format, and stat-only modes. |
| GIT-05 | `git add` | `rtk/src/cmds/git/git.rs` | `git.add` | Yes | Fixed in PTK | fixed | PTK now follows successful adds with cached diff shortstat output so the filter can emit RTK-style `ok <shortstat>` summaries while still preserving warnings and failures. |
| GIT-06 | `git commit` | `rtk/src/cmds/git/git.rs` | `git.commit` | Yes | Conforms | reviewed | Both sides reduce successful commits to a compact `ok` plus short hash, preserve failures, and special-case nothing-to-commit situations. |
| GIT-07 | `git push` | `rtk/src/cmds/git/git.rs` | `git.push` | Yes | Conforms | reviewed | Both sides collapse successful pushes to an up-to-date message or pushed ref target and leave failures uncompressed. |
| GIT-08 | `git pull` | `rtk/src/cmds/git/git.rs` | `git.pull` | Yes | Conforms | reviewed | Both sides summarize successful pulls as up-to-date or compact file/change counts. |
| GIT-09 | `git branch` | `rtk/src/cmds/git/git.rs` | `git.branch` | Yes | Fixed in PTK | fixed | PTK now distinguishes default list, show-current, and mutating branch modes, injects `-a --no-color` for default listing, and formats remote-only branches separately like RTK. |
| GIT-10 | `git fetch` | `rtk/src/cmds/git/git.rs` | `git.fetch` | Yes | Conforms | reviewed | Both sides count updated refs from fetch output and reduce success to a compact fetched summary. |
| GIT-11 | `git stash` | `rtk/src/cmds/git/git.rs` | `git.stash` | Yes | Fixed in PTK | fixed | PTK now follows RTK's stash subcommand split for `list`, `show`, `pop`/`apply`/`drop`/`push`, and default stash behavior instead of applying one generic summarizer. |
| GIT-12 | `git worktree` | `rtk/src/cmds/git/git.rs` | `git.worktree` | Yes | Fixed in PTK | fixed | PTK now distinguishes worktree list mode from mutating subcommands, rewrites bare `git worktree` to `list`, and reduces successful mutations to `ok` like RTK. |
| GH-01 | `gh pr list` | `rtk/src/cmds/git/gh_cmd.rs` | `gh.pr.list` | Yes | Fixed in PTK | fixed | PTK now rewrites default `gh pr list` execution to RTK-style forced JSON fields, preserves explicit structured-output passthrough, and formats compact PR rows from structured data. |
| GH-02 | `gh pr view` | `rtk/src/cmds/git/gh_cmd.rs` | `gh.pr.view` | Yes | Fixed in PTK | fixed | PTK now rewrites default `gh pr view` execution to forced JSON fields, preserves RTK passthrough cases such as structured output and `--web`/`--comments`, and summarizes mergeability, reviews, checks, URL, and filtered body from structured data. |
| GH-03 | `gh issue list` | `rtk/src/cmds/git/gh_cmd.rs` | `gh.issue.list` | Yes | Fixed in PTK | fixed | PTK now rewrites default `gh issue list` execution to forced JSON fields and formats normalized issue rows from structured fields instead of compacting rendered tables only. |
| GH-04 | `gh run list` | `rtk/src/cmds/git/gh_cmd.rs` | `gh.run.list` | Yes | Fixed in PTK | fixed | PTK now rewrites default `gh run list` execution to forced JSON with the RTK-like default limit and formats workflow runs from structured status/conclusion data. |
| GH-05 | Other `gh` summaries: repo, API, generic JSON modes | `rtk/src/cmds/git/gh_cmd.rs` | `gh` | Yes | Fixed in PTK | fixed | PTK now routes general `gh` commands through the GitHub filter, adds `gh repo view` summarization, preserves explicit `gh api` payloads, and keeps structured `--json`/`--jq`/`--template` flows raw. |
| GT-01 | `gt log` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.log` | Yes | Fixed in PTK | fixed | PTK now ships a real Graphite `gt` filter family and wrapper surface; `gt log` strips emails, keeps the graph entries, and truncates long stacks similarly to the reviewed RTK slice. |
| GT-02 | `gt submit` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.submit` | Yes | Fixed in PTK | fixed | PTK now summarizes Graphite submit flows into pushed branches plus created/updated PR rows instead of leaving the command family unimplemented. |
| GT-03 | `gt sync` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.sync` | Yes | Fixed in PTK | fixed | PTK now summarizes `gt sync` into synced/deleted counts and deleted branch names via a dedicated Graphite reducer. |
| GT-04 | `gt restack` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.restack` | Yes | Fixed in PTK | fixed | PTK now summarizes Graphite restack output into compact branch-count confirmations instead of generic fallback output. |
| GT-05 | `gt create` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.create` | Yes | Fixed in PTK | fixed | PTK now summarizes Graphite branch creation into a compact `ok created <branch>` confirmation, matching the reviewed RTK slice. |
| GT-06 | `gt branch` | `rtk/src/cmds/git/gt_cmd.rs` | `gt.branch` | Yes | Fixed in PTK | fixed | PTK now exposes a real `pytk-ai gt` wrapper surface and preserves plain `gt branch` output while also remapping git-like Graphite passthrough subcommands to PTK's existing git reducers. |
| DIFF-01 | Standalone file diff condenser | `rtk/src/cmds/git/diff_cmd.rs` | `files.diff` | Yes | Fixed in PTK | fixed | PTK now rewrites plain two-path `diff` invocations to unified diff execution and formats direct file-to-file comparisons with RTK-style added/removed headers while preserving the existing unified-diff condenser path. |

### Rust, JS, TS, And Generic Test Wrappers

| ID | RTK Unit | RTK Source | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CARGO-01 | `cargo build` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.build` | Yes | Conforms | reviewed | Both sides strip compile/download noise, count compiled crates, and group cargo diagnostics into compact build summaries. |
| CARGO-02 | `cargo clippy` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.clippy` | Yes | Fixed in PTK | fixed | PTK now uses a dedicated clippy reducer that groups warnings by lint rule, preserves location context, and reports error details separately instead of reusing the generic cargo build summarizer. |
| CARGO-03 | `cargo fmt` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.fmt` | Partial | Known scope gap | reviewed | The RTK inventory lists `cargo fmt`, but the current RTK Rust command module appears not to expose a dedicated fmt handler and repository discovery classifies `cargo fmt` as passthrough; PTK does have a dedicated `cargo.fmt` summary, so this is an RTK-inventory/code mismatch rather than a PTK implementation gap. |
| CARGO-04 | `cargo check` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.build` | Yes | Conforms | reviewed | RTK `run_check()` reuses `filter_cargo_build`; PTK routes `cargo check` through the same build-style diagnostic summarizer, so the reuse is materially aligned. |
| CARGO-05 | `cargo test` | `rtk/src/cmds/rust/cargo_cmd.rs` | `test.cargo` | Yes | Fixed in PTK | fixed | PTK `test.cargo` now aggregates multiple cargo test suite summaries into one compact result and remaps compile-error output through the cargo diagnostic summarizer with a `cargo test:` label. |
| CARGO-06 | `cargo install` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.install` | Yes | Fixed in PTK | fixed | PTK now emits an install-specific cargo summary for successful installs, already-installed cases, replacement/warning notes, and grouped install errors instead of falling back to the generic cargo build formatter. |
| CARGO-07 | `cargo nextest` | `rtk/src/cmds/rust/cargo_cmd.rs` | `cargo.nextest` | Yes | Fixed in PTK | fixed | PTK now routes `cargo nextest` through a dedicated nextest parser that strips build noise and summarizes failures, binaries, skips, and cancellations instead of falling back to cargo build diagnostics. |
| RUNNER-01 | Errors-only wrapper: `rtk err` | `rtk/src/cmds/rust/runner.rs` | `err` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai err` wrapper surface in the CLI and runner that executes arbitrary commands and reduces output to errors/warnings-focused lines instead of relying on generic fallback ordering alone. |
| RUNNER-02 | Failures-only wrapper: `rtk test` | `rtk/src/cmds/rust/runner.rs` | `test.generic`, `test.cargo` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai test` wrapper surface in the CLI and runner, reuses existing pytest/go/rspec/cargo reducers for wrapped commands, and preserves generic failures-only extraction for other test runners. |
| JS-01 | JS lint grouping: ESLint and Biome | `rtk/src/cmds/js/lint_cmd.rs` | `lint.eslint`, `lint.biome` | Yes | Fixed in PTK | fixed | PTK now matches the reviewed RTK lint slice more closely by routing wrapper-prefixed ESLint/Biome commands (`pnpm exec`, `npm exec`, `yarn`, `bunx`) to the lint filter, keeping grouped ESLint summaries, and stripping Biome check noise while preserving either compact grouped diagnostics or the meaningful Biome diagnostic block. |
| JS-02 | TypeScript compiler grouping | `rtk/src/cmds/js/tsc_cmd.rs` | `tsc` | Yes | Conforms | reviewed | Both sides group TypeScript compiler diagnostics by file and code with preserved context lines. |
| JS-03 | `next build` summary | `rtk/src/cmds/js/next_cmd.rs` | `next.build` | Yes | Conforms | reviewed | Both sides collapse Next.js build output into route counts, top bundle sizes, timing, and warning/error totals. |
| JS-04 | Prettier output filter | `rtk/src/cmds/js/prettier_cmd.rs` | `format.prettier` | Yes | Fixed in PTK | fixed | PTK `format.prettier` now handles both check-mode and write-mode output, including wrapper-prefixed invocations, file lists needing formatting, formatted-file summaries, and the same compact clean-success reduction at the reviewed RTK granularity. |
| JS-05 | Playwright test filter | `rtk/src/cmds/js/playwright_cmd.rs` | `playwright` | Yes | Fixed in PTK | fixed | PTK now backs `pytk-ai playwright` with a command-aware reducer that prefers structured Playwright JSON when present, keeps compact failure details, and falls back to summarized text output instead of generic noise. |
| JS-06 | Vitest test filter | `rtk/src/cmds/js/vitest_cmd.rs` | `vitest` | Yes | Fixed in PTK | fixed | PTK now backs `pytk-ai vitest` with a command-aware reducer that prefers structured Vitest/Jest-style JSON when present, preserves failure details and duration, and falls back to summarized text output instead of generic cleanup. |
| JS-07 | Prisma generate | `rtk/src/cmds/js/prisma_cmd.rs` | `prisma.generate` | Yes | Conforms | reviewed | Both sides remove Prisma decoration and emit a compact generate summary with generated-client confirmation plus model/enum/type counts and output target when present. |
| JS-08 | Prisma migrate flows | `rtk/src/cmds/js/prisma_cmd.rs` | `package` (`prisma.migrate-*`) | Yes | Fixed in PTK | fixed | PTK now routes `prisma migrate dev/status/deploy` through the package filter and emits compact migrate summaries with migration name/count extraction instead of falling back to generic output. |
| JS-09 | Prisma db push | `rtk/src/cmds/js/prisma_cmd.rs` | `package` (`prisma.db-push`) | Yes | Fixed in PTK | fixed | PTK now routes `prisma db push` and emits a compact schema-push summary with table/column/index counts. |
| JS-10 | `pnpm list` | `rtk/src/cmds/js/pnpm_cmd.rs` | `pnpm.list` | Yes | Conforms | reviewed | RTK and PTK both provide a dedicated dependency-list summarizer for `pnpm list`, preferring structured data when available and falling back to compact dependency rows. |
| JS-11 | `pnpm outdated` | `rtk/src/cmds/js/pnpm_cmd.rs` | `package` (`pnpm.outdated`) | Yes | Fixed in PTK | fixed | PTK now routes `pnpm outdated` through the package filter and summarizes current/wanted/latest versions instead of generic fallback output. |
| JS-12 | `pnpm install` | `rtk/src/cmds/js/pnpm_cmd.rs` | `package` (`pnpm.install`) | Yes | Fixed in PTK | fixed | PTK now routes `pnpm install` and strips progress noise while keeping install summaries and added/removed package lines. |
| JS-13 | npm boilerplate stripping and run output cleanup | `rtk/src/cmds/js/npm_cmd.rs` | `package` (`npm.run`) | Yes | Fixed in PTK | fixed | PTK now routes `npm run`/`npm exec` through package-aware cleanup that removes npm boilerplate, notices, and warnings while preserving command output. |
| JS-14 | Universal format dispatcher | `rtk/src/cmds/system/format_cmd.rs` | `format`, `python.ruff` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai format` wrapper surface with RTK-style formatter auto-detection (`prettier`, `black`, `ruff`, `biome`), small default-flag injection, current-directory fallback, and reuse of the existing formatter-specific reducers for Prettier, Black, Biome, and Ruff format output. |

### Python, Go, Ruby, .NET, Cloud, And System

| ID | RTK Unit | RTK Source | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PY-01 | Ruff diagnostics summary | `rtk/src/cmds/python/ruff_cmd.rs` | `python.ruff` | Yes | Conforms | reviewed | Both sides summarize Ruff check diagnostics from structured output with issue counts, top rules, top files, and fixable-item reporting. |
| PY-02 | Ruff formatter output | `rtk/src/cmds/python/ruff_cmd.rs` | `python.ruff` | Yes | Fixed in PTK | fixed | PTK now detects Ruff formatter check/write flows separately from Ruff diagnostics and emits dedicated formatter summaries for files needing formatting, reformatted-file counts, and clean formatter runs. |
| PY-03 | Pytest failure summary | `rtk/src/cmds/python/pytest_cmd.rs` | `python.pytest` | Yes | Conforms | reviewed | Both sides retain pytest failure sections and compact success to a passed summary while dropping most progress noise. |
| PY-04 | Mypy grouping | `rtk/src/cmds/python/mypy_cmd.rs` | `python.mypy` | Yes | Conforms | reviewed | Both sides group mypy diagnostics by file, preserve attached notes, and summarize top error codes. |
| PY-05 | Pip list | `rtk/src/cmds/python/pip_cmd.rs` | `pip.list` | Yes | Conforms | reviewed | Both sides prefer JSON package listings and return a compact package/version summary for `pip list`. |
| PY-06 | Pip outdated | `rtk/src/cmds/python/pip_cmd.rs` | `pip.outdated` | Yes | Conforms | reviewed | Both sides prefer JSON outdated output and summarize current-to-latest upgrades compactly. |
| GO-01 | `go test` | `rtk/src/cmds/go/go_cmd.rs` | `go.test` | Yes | Conforms | reviewed | Both sides emit package-oriented go test summaries with failed test details and build-failure surfacing, even though RTK gets there via forced `-json`. |
| GO-02 | `go build` | `rtk/src/cmds/go/go_cmd.rs` | `go.build` | Yes | Conforms | reviewed | Both sides reduce `go build` to success or a compact list of Go build error lines. |
| GO-03 | `go vet` | `rtk/src/cmds/go/go_cmd.rs` | `go.vet` | Yes | Conforms | reviewed | Both sides keep only vet issue lines and emit a compact clean/no-issues result otherwise. |
| GO-04 | `golangci-lint` | `rtk/src/cmds/go/golangci_cmd.rs` | `golangci-lint` | Yes | Fixed in PTK | fixed | PTK now rewrites `golangci-lint` runs to structured JSON output with v1/v2-compatible execution paths and summarizes issues by linter/file with source-line previews when available. |
| RB-01 | Rake / Rails Minitest output | `rtk/src/cmds/ruby/rake_cmd.rs` | `rake` | Yes | Fixed in PTK | fixed | PTK now backs `pytk-ai rake` with a Minitest-aware reducer that summarizes passing runs and keeps compact failure/error details for `rake test` and Rails-style test output instead of generic fallback. |
| RB-02 | RSpec failure summary | `rtk/src/cmds/ruby/rspec_cmd.rs` | `rspec` | Yes | Fixed in PTK | fixed | PTK now rewrites default RSpec execution to JSON, reports duration and pending counts, keeps compact failed-example details, and still falls back to a cleaner text parser when structured output is unavailable. |
| RB-03 | RuboCop grouping | `rtk/src/cmds/ruby/rubocop_cmd.rs` | `rubocop` | Yes | Fixed in PTK | fixed | PTK now rewrites default RuboCop execution to JSON, sorts offenses by severity/file, and tracks correctable/autocorrect metadata instead of relying only on plain-text grouping. |
| DN-01 | `dotnet build` | `rtk/src/cmds/dotnet/dotnet_cmd.rs` | `dotnet.build` | Yes | Fixed in PTK | fixed | PTK now backs the existing `dotnet` rewrite with a real `.NET` filter family and wrapper surface, summarizing build success/failure with project counts, duration, and compact grouped diagnostics. |
| DN-02 | `dotnet test` | `rtk/src/cmds/dotnet/dotnet_cmd.rs` | `dotnet.test` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai dotnet` wrapper surface for test runs and summarizes pass/fail counts, duration, failed tests, and attached build diagnostics instead of generic fallback output. |
| DN-03 | `dotnet restore` | `rtk/src/cmds/dotnet/dotnet_cmd.rs` | `dotnet.restore` | Yes | Fixed in PTK | fixed | PTK now summarizes `dotnet restore` with restored-project counts, duration, and compact grouped errors/warnings rather than leaving the command family unimplemented. |
| DN-04 | `dotnet format` | `rtk/src/cmds/dotnet/dotnet_cmd.rs` | `dotnet.format` | Yes | Fixed in PTK | fixed | PTK now summarizes `dotnet format` check/write flows with files needing formatting or files formatted, using a dedicated `.NET` formatter reducer instead of falling back to generic output. |
| CLD-01 | AWS read/list/describe summaries | `rtk/src/cmds/cloud/aws_cmd.rs` | `aws.read` | Yes | Conforms | reviewed | Both sides force or prefer structured AWS read output where applicable and emit service-specific compact summaries for STS identity, EC2, S3 listings, and common collection payloads. |
| CLD-02 | `docker ps` | `rtk/src/cmds/cloud/container.rs` | `docker.ps` | Yes | Conforms | reviewed | Both sides parse compact table output for containers and summarize id/name/image/ports in materially the same way. |
| CLD-03 | `docker images` | `rtk/src/cmds/cloud/container.rs` | `docker.images` | Yes | Conforms | reviewed | Both sides summarize image names and aggregate total size from compact tabular output. |
| CLD-04 | `docker logs` | `rtk/src/cmds/cloud/container.rs` | `docker.logs` | Yes | Conforms | reviewed | Both sides keep mostly raw logs but deduplicate repeated lines and label the selected container target. |
| CLD-05 | `docker compose ps` | `rtk/src/cmds/cloud/container.rs` | `docker.compose.ps` | Yes | Conforms | reviewed | Both sides use structured compose-ps rows to emit compact service/image/status/ports summaries. |
| CLD-06 | `docker compose logs` | `rtk/src/cmds/cloud/container.rs` | `docker.compose.logs` | Yes | Fixed in PTK | fixed | PTK now routes `docker compose logs` into the infra filter, labels the target service, and reuses the existing repeated-line collapse behavior for compact compose log summaries. |
| CLD-07 | `docker compose build` | `rtk/src/cmds/cloud/container.rs` | `docker.compose.build` | Yes | Fixed in PTK | fixed | PTK now routes `docker compose build` into the infra filter and summarizes the build header, discovered services, and step count instead of falling back to generic output. |
| CLD-08 | `kubectl pods` | `rtk/src/cmds/cloud/container.rs` | `kubectl.pods` | Yes | Conforms | reviewed | Both sides parse structured pod output and summarize running/pending/failed pod counts plus restart/issue highlights. |
| CLD-09 | `kubectl services` | `rtk/src/cmds/cloud/container.rs` | `kubectl.services` | Yes | Conforms | reviewed | Both sides summarize Kubernetes services from structured output with namespace/type/port information. |
| CLD-10 | `kubectl logs` | `rtk/src/cmds/cloud/container.rs` | `kubectl.logs` | Yes | Conforms | reviewed | Both sides preserve mostly raw pod logs while deduplicating repeats and labeling the selected target. |
| CLD-11 | Curl JSON / schema summary | `rtk/src/cmds/cloud/curl_cmd.rs` | `curl` | Yes | Conforms | reviewed | Both sides schema-summarize JSON only when that is shorter than the original payload and otherwise preserve compact raw text. |
| CLD-12 | Wget summary | `rtk/src/cmds/cloud/wget_cmd.rs` | `wget` | Yes | Conforms | reviewed | Both sides compress successful downloads to URL/file/size and map common failures to compact reasons. |
| CLD-13 | PSQL compact tabular output | `rtk/src/cmds/cloud/psql_cmd.rs` | `psql` | Yes | Fixed in PTK | fixed | PTK now ships a dedicated `psql` reducer for normal table and expanded-record output and exposes a real `pytk-ai psql` wrapper surface instead of falling back to generic cleanup. |
| SYS-01 | `ls` compact listing | `rtk/src/cmds/system/ls.rs` | `system.ls` | Yes | Conforms | reviewed | Both sides run long-form listing logic, hide common noise unless all-files flags are present, and emit compact entries plus a summary. |
| SYS-02 | `tree` compaction | `rtk/src/cmds/system/tree.rs` | `files.tree` | Yes | Conforms | reviewed | RTK mainly strips the final summary line and auto-ignores noise directories, while PTK keeps that summary plus a short preview; both materially provide a compact tree view of the same command family. |
| SYS-03 | `read` command with filtering and windowing | `rtk/src/cmds/system/read.rs` | `read`, `system.read.*` | Yes | Fixed in PTK | fixed | PTK now exposes a first-class `pytk-ai read` command with filter-level selection, structure-aware max-line truncation, tail/max-line windowing, stdin support, and optional line numbering, while preserving the existing raw-ish `cat`/`head`/`tail` path. |
| SYS-04 | JSON viewer / schema mode | `rtk/src/cmds/system/json_cmd.rs` | `json.compact`, `json.schema` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai json` surface with compact-vs-schema rendering, extension validation, and depth control instead of only opportunistic JSON shaping in other command families. |
| SYS-05 | Grep grouping | `rtk/src/cmds/system/grep_cmd.rs` | `search.grep` | Yes | Conforms | reviewed | Both sides group grep hits by file, count total matches, and keep only a bounded sample of matching lines. |
| SYS-06 | Find grouping | `rtk/src/cmds/system/find_cmd.rs` | `search.find` | Yes | Fixed in PTK | fixed | PTK now rewrites supported `find` cases into a command-aware Python walker that handles `-name`/`-iname`, `-type`, `-maxdepth`, hidden/noise pruning, grouped directory output, and extension summaries instead of only compacting raw shell output. |
| SYS-07 | Log deduplication | `rtk/src/cmds/system/log_cmd.rs` | `log` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai log` surface that normalizes timestamps/IDs and groups repeated error/warn patterns into compact summaries instead of relying only on generic repeated-line collapse. |
| SYS-08 | Environment masking | `rtk/src/cmds/system/env_cmd.rs` | `env` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai env` surface that groups interesting variables, masks sensitive values by default, and truncates noisy values instead of exposing only raw environment output. |
| SYS-09 | Dependency manifest summary | `rtk/src/cmds/system/deps.rs` | `deps` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai deps` surface that summarizes common dependency manifests (`Cargo.toml`, `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`) instead of lacking any manifest overview path. |
| SYS-10 | Heuristic arbitrary-command summary | `rtk/src/cmds/system/summary.rs` | `summary` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai summary` surface that runs arbitrary commands and shapes the output heuristically by type instead of always falling back to generic cleanup only. |
| SYS-11 | Word / line / byte counts | `rtk/src/cmds/system/wc_cmd.rs` | `files.wc` | Yes | Conforms | reviewed | Both sides parse requested `wc` columns, compact single-file output, and summarize totals across multi-file runs while stripping redundant path prefixes. |
| SYS-12 | Local LLM / heuristic file summary | `rtk/src/cmds/system/local_llm.rs` | `smart` | Yes | Fixed in PTK | fixed | PTK now ships a real `pytk-ai smart` surface that produces a two-line heuristic source summary without any external model instead of lacking the command-aware surface entirely. |

## Built-In RTK TOML Filters

### Build, Lint, And Formatter TOML Filters

| ID | RTK TOML Filter | Match Area | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOML-BLD-01 | `ansible-playbook.toml` | `ansible-playbook` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-02 | `basedpyright.toml` | `basedpyright` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-03 | `biome.toml` | `biome` | `lint.biome`, `format.biome` | Yes | Fixed in PTK | fixed | RTK's built-in `biome.toml` filter is a narrow `^biome\b` cleanup rule set (`Checked ...`/`Fixed ...`/helper-hint stripping plus `on_empty = biome: ok`); PTK now materially covers that audited slice command-aware across Biome lint and formatter flows even though the broader generic TOML fallback engine remains a separate `CORE-01` architectural gap. |
| TOML-BLD-04 | `dotnet-build.toml` | `dotnet build` | `-` | No | Missing in PTK | todo | No PTK `.NET` filter family. |
| TOML-BLD-05 | `gcc.toml` | `gcc`, `g++` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-06 | `gradle.toml` | `gradle`, `gradlew` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-07 | `hadolint.toml` | `hadolint` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-08 | `make.toml` | `make` | `test.generic` | Partial | Known scope gap | todo | PTK only recognizes `make test`, not general `make` build noise. |
| TOML-BLD-09 | `markdownlint.toml` | `markdownlint` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-10 | `mix-compile.toml` | `mix compile` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-11 | `mix-format.toml` | `mix format` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-12 | `mvn-build.toml` | Maven build flows | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-13 | `nx.toml` | `nx` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-14 | `oxlint.toml` | `oxlint` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-15 | `pio-run.toml` | `pio run` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-16 | `pre-commit.toml` | `pre-commit` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-17 | `quarto-render.toml` | `quarto render` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-18 | `shellcheck.toml` | `shellcheck` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-19 | `shopify-theme.toml` | `shopify theme push/pull` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-20 | `spring-boot.toml` | Spring Boot startup | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-21 | `swift-build.toml` | `swift build` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-22 | `task.toml` | `task` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-23 | `trunk-build.toml` | `trunk build` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-24 | `turbo.toml` | `turbo` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-25 | `ty.toml` | `ty` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-26 | `xcodebuild.toml` | `xcodebuild` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-BLD-27 | `yamllint.toml` | `yamllint` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |

### Package Manager And Dependency TOML Filters

| ID | RTK TOML Filter | Match Area | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOML-PKG-01 | `brew-install.toml` | `brew install`, `brew upgrade` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-PKG-02 | `bundle-install.toml` | `bundle install`, `bundle update` | `package` (`bundle.install`, `bundle.update`) | Yes | Fixed in PTK | fixed | PTK now recognizes both `bundle install` and `bundle update` in hint inference and planning rules, preserving the existing bundle summaries for both flows. |
| TOML-PKG-03 | `composer-install.toml` | Composer install/update/require | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-PKG-04 | `mise.toml` | `mise` install/run flows | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-PKG-05 | `poetry-install.toml` | Poetry install/lock/update | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-PKG-06 | `uv-sync.toml` | `uv sync`, `uv pip install` | `package` (`uv.sync`, `uv.pip-install`) | Yes | Fixed in PTK | fixed | PTK now covers the full RTK TOML scope by routing `uv pip install` through the package filter and stripping download/cache noise while keeping install summaries. |

### Infra, Cloud, And DevOps TOML Filters

| ID | RTK TOML Filter | Match Area | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOML-INF-01 | `fail2ban-client.toml` | `fail2ban-client` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-02 | `gcloud.toml` | `gcloud` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-03 | `helm.toml` | `helm` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-04 | `iptables.toml` | `iptables` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-05 | `rsync.toml` | `rsync` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-06 | `skopeo.toml` | `skopeo` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-07 | `sops.toml` | `sops` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-08 | `ssh.toml` | `ssh` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-09 | `systemctl-status.toml` | `systemctl status` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-10 | `terraform-plan.toml` | `terraform plan` | `terraform.plan` | Yes | Conforms | reviewed | PTK's `terraform.plan` filter removes the same refresh/lock/blank noise and preserves the meaningful plan or no-changes message, materially matching the RTK TOML filter behavior. |
| TOML-INF-11 | `tofu-fmt.toml` | `tofu fmt` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-12 | `tofu-init.toml` | `tofu init` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-INF-13 | `tofu-plan.toml` | `tofu plan` | `-` | No | Missing in PTK | todo | PTK only targets `terraform plan`, not OpenTofu. |
| TOML-INF-14 | `tofu-validate.toml` | `tofu validate` | `-` | No | Missing in PTK | todo | PTK only targets `terraform validate`, not OpenTofu. |

### System, Shell, And Utility TOML Filters

| ID | RTK TOML Filter | Match Area | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOML-SYS-01 | `df.toml` | `df` | `toml.df` | Yes | Conforms | reviewed | Verified stale row: PTK's bounded built-in TOML fallback matches RTK's reviewed `df.toml` slice on the generic path, including wide-line truncation and max-line capping. |
| TOML-SYS-02 | `du.toml` | `du` | `toml.du` | Yes | Conforms | reviewed | Verified stale row: PTK's bounded built-in TOML fallback matches RTK's reviewed `du.toml` slice on the generic path, including blank-line stripping and bounded output. |
| TOML-SYS-03 | `jq.toml` | `jq` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-SYS-04 | `jj.toml` | `jj` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-SYS-05 | `just.toml` | `just` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-SYS-06 | `ollama.toml` | `ollama run` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-SYS-07 | `ping.toml` | `ping` | `toml.ping` | Yes | Conforms | reviewed | Verified stale row: PTK's bounded built-in TOML fallback matches RTK's reviewed `ping.toml` slice on the generic path, dropping per-packet chatter and keeping the bounded tail summary. |
| TOML-SYS-08 | `ps.toml` | `ps` | `toml.ps` | Yes | Conforms | reviewed | Verified stale row: PTK's bounded built-in TOML fallback matches RTK's reviewed `ps.toml` slice on the generic path, including wide-line truncation and row limits. |
| TOML-SYS-09 | `stat.toml` | `stat` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |
| TOML-SYS-10 | `yadm.toml` | `yadm` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |

### Miscellaneous TOML Filters

| ID | RTK TOML Filter | Match Area | PTK Target | PTK Coverage | Conformance | Work State | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOML-MISC-01 | `jira.toml` | `jira` | `-` | No | Missing in PTK | todo | No command-aware PTK filter. |

## Findings Log

Use this format for updates:

```text
### <date> <agent/session>
- Reviewed IDs: ...
- Result: Conforms / Discrepant / Missing / Fixed
- Evidence:
- Findings:
- Follow-up:
```

### 2026-04-05 codex
- Reviewed IDs: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05
- Result: Known scope gap / Missing
- Evidence:
- `rtk/src/core/toml_filter.rs` implements a registry with project, user-global, and built-in TOML filters plus an eight-stage declarative pipeline (`strip_ansi`, `replace`, `match_output`, line keep/strip, line truncation, head/tail, `max_lines`, `on_empty`).
- `src/pytk_ai/filters/base.py` and `src/pytk_ai/filters/generic.py` only provide shared cleanup (`strip_ansi`, blank/repeated-line collapse, generic truncation) and generic dispatch, with no TOML loading or declarative rule engine.
- `rtk/src/core/filter.rs` defines `FilterLevel::None`, `Minimal`, and `Aggressive`, plus `smart_truncate()`; `rtk/src/cmds/system/read.rs` wires those into `rtk read` with `max_lines`, `tail_lines`, and optional line numbers.
- `src/pytk_ai/plan/normalize.py` only routes `cat`, `head`, `tail`, and `pytk-ai read` to the `read` filter hint, and `src/pytk_ai/filters/files.py` keeps raw-ish output with simple truncation and repeated-line collapse.
- Findings:
- CORE-01 is a real architectural gap, not just an inventory mismatch: PTK has overlapping cleanup primitives but no RTK-style TOML fallback engine.
- CORE-02 is partial because PTK can surface raw reads, but its read path does not model RTK's explicit filter-level and windowing contract.
- CORE-03 and CORE-04 are missing in PTK because no PTK mode applies RTK's language-aware minimal/aggressive source filtering.
- CORE-05 is a scope gap because PTK truncation is generic line-based truncation rather than RTK's structure-aware file truncation.
- Follow-up:
- Add a PTK follow-up for declarative fallback filtering and separate follow-up(s) for richer `read` semantics, including filter levels and structural truncation.

### 2026-04-05 codex
- Reviewed IDs: CARGO-04, CARGO-05, CARGO-06, CARGO-07, GH-05, JS-07, JS-08, JS-09, JS-10, JS-11, JS-12, JS-13, JS-14, PY-02, CLD-06, CLD-07, SYS-03
- Result: Conforms / Known scope gap / Missing
- Evidence:
- `rtk/src/cmds/rust/cargo_cmd.rs` shows `run_check()` reusing `filter_cargo_build()`, while `run_test()`, `run_install()`, and `run_nextest()` use dedicated parsers for test aggregation, install summaries, and nextest summaries.
- `src/pytk_ai/plan/normalize.py` only gives special handling to `cargo build|clippy|check|fmt` and `cargo test`; `cargo install` and `cargo nextest` fall through to the top-level `cargo` hint and therefore the generic cargo/build summarizer in `src/pytk_ai/filters/build.py`.
- `rtk/src/cmds/git/gh_cmd.rs` has dedicated `run_repo()` handling plus explicit `run_api()` passthrough behavior; `src/pytk_ai/plan/normalize.py` only recognizes `gh pr list/view`, `gh issue list`, and `gh run list`, while `src/pytk_ai/filters/github_api.py` has no repo/api mode.
- `rtk/src/cmds/js/prisma_cmd.rs` implements `generate`, `migrate dev/status/deploy`, and `db push`; `src/pytk_ai/filters/packages.py` and `src/pytk_ai/plan/normalize.py` only recognize `prisma generate`.
- `rtk/src/cmds/js/pnpm_cmd.rs` implements `list`, `outdated`, and `install`, and `rtk/src/cmds/js/npm_cmd.rs` strips generic npm boilerplate; PTK only recognizes `npm/pnpm list` in `src/pytk_ai/plan/normalize.py`.
- `rtk/src/cmds/system/format_cmd.rs` dispatches formatter output, while PTK has no equivalent formatter-dispatch command surface.
- `rtk/src/cmds/python/ruff_cmd.rs` has separate check and formatter reducers; `src/pytk_ai/filters/python.py` only emits a Ruff issue summary when it can parse lint-style output and otherwise falls back to generic text.
- `rtk/src/cmds/cloud/container.rs` has dedicated `format_compose_logs()` and `format_compose_build()` paths; PTK `src/pytk_ai/filters/infra.py` only recognizes `docker compose ps`.
- Findings:
- CARGO-04 is conformant because RTK itself treats `cargo check` as a build-filter reuse case; PTK's reuse matches that design.
- CARGO-05, CARGO-06, and CARGO-07 are real scope gaps because PTK either uses a much simpler cargo-test reducer or routes install/nextest through the wrong summarizer.
- GH-05 is missing in PTK rather than partial coverage: generic `gh` commands do not reach PTK's GitHub filter at all unless they are one of the explicitly recognized list/view cases.
- JS-07 and JS-10 conform at the current review granularity; JS-08/09/11/12/13/14 are missing in PTK due to absent command-aware routing and summarizers.
- PY-02 is a narrower PTK implementation, not a total absence, because Ruff commands are routed but formatter-specific interpretation is missing.
- CLD-06 and CLD-07 are missing in PTK because compose logs/build never hit a specialized infra path.
- SYS-03 remains a real scope gap and aligns with the earlier core `read` findings.
- Follow-up:
- Add dedicated PTK routing/parsers for `cargo install`, `cargo nextest`, generic `gh` repo/api handling, Prisma migrate/db-push, pnpm outdated/install, npm boilerplate stripping, formatter dispatch, Ruff format, and Docker Compose logs/build.

### 2026-04-05 codex
- Reviewed IDs: CARGO-05
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/rust/cargo_cmd.rs` before editing: RTK aggregates multiple `test result:` lines when all suites pass and remaps compile-only failures through `filter_cargo_build()` with a `cargo test:` prefix.
- Updated `src/pytk_ai/filters/tests.py` so PTK now parses and aggregates multiple cargo suite summaries and reuses the cargo build summarizer for compile-error-only failures.
- Added regression coverage in `tests/test_filters_tests.py` for multi-suite aggregation and compile-error fallback.
- Findings:
- PTK now matches the reviewed RTK behaviors that motivated `CARGO-05`: multi-suite pass aggregation and compile-error remapping.
- Existing failure-focused behavior for failing test suites remains intact.
- Follow-up:
- Remove `CARGO-05` from the fix queue. Remaining Cargo follow-up work is limited to `cargo install` and `cargo nextest`.

### 2026-04-06 codex
- Reviewed IDs: CORE-03, CORE-04
- Result: Conforms
- Evidence:
- Re-read `rtk/src/core/filter.rs` and `rtk/src/cmds/system/read.rs`: RTK minimal mode strips language-aware comments while preserving doc comments/docstrings and blank-line normalization; aggressive mode builds on minimal mode to keep imports, signatures, braces, and top-level const/static-like declarations while eliding bodies.
- Re-read `src/pytk_ai/filters/files.py` and `src/pytk_ai/cli.py`: PTK already exposes `pytk-ai read --level minimal|aggressive`, and `render_read_output()` routes those levels through Python implementations that materially match the audited RTK slice.
- Added regression coverage in `tests/test_filters_files.py` and `tests/test_live_system.py` proving minimal-mode doc preservation/comment stripping and aggressive-mode structure retention/body elision through both direct rendering and live `run_command("pytk-ai read ...")` execution.
- Findings:
- `CORE-03` and `CORE-04` were stale workboard rows, not live PTK gaps.
- PTK already had command-aware parity for the reviewed RTK slice; this batch only needed evidence-backed tests and status correction.
- Follow-up:
- `CORE-01` remains the separate unresolved core architectural gap for RTK's TOML fallback engine; no further action is needed for `CORE-03` or `CORE-04` at the reviewed granularity.

### 2026-04-06 codex
- Reviewed IDs: TOML-SYS-01, TOML-SYS-02, TOML-SYS-07, TOML-SYS-08
- Result: Conforms
- Evidence:
- Re-read `rtk/src/filters/df.toml`, `du.toml`, `ping.toml`, and `ps.toml`: the audited RTK slices are bounded declarative rules only, covering line stripping, line truncation, tail preservation, and line-count caps for these four commands.
- Re-read `src/pytk_ai/filters/toml_fallback.py`, `src/pytk_ai/filters/generic.py`, and `src/pytk_ai/filters/__init__.py`: PTK's generic path now loads repo-backed built-in RTK TOML filters, matches by `match_command`, and applies the same reviewed bounded transform stages before returning `toml.<name>` filter results.
- Added regression coverage in `tests/test_filters_generic.py` proving `filter_output()` reaches the built-in TOML fallback for `df`, `du`, `ping`, and `ps` and preserves the reviewed RTK behaviors for truncation, blank-line stripping, tail-summary retention, and row caps.
- Findings:
- `TOML-SYS-01`, `TOML-SYS-02`, `TOML-SYS-07`, and `TOML-SYS-08` were stale workboard rows after Batch 19's bounded built-in TOML fallback landed; they are not live PTK gaps.
- No new command-specific wrapper or filter code was required for this batch because the generic fallback engine already materially covers these RTK TOML rows.
- Follow-up:
- `CORE-01` remains open for broader RTK TOML registry semantics beyond the bounded built-in fallback, but no residual row-specific gap remains for these four system TOML filters at the reviewed granularity.

### 2026-04-05 codex
- Reviewed IDs: CARGO-06
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/rust/cargo_cmd.rs` before editing: RTK has a dedicated `filter_cargo_install()` that strips dependency churn, recognizes already-installed cases, keeps replacement/actionable warning lines, and groups install errors.
- Updated `src/pytk_ai/filters/build.py` to detect `cargo install` separately and emit `cargo.install` summaries for success, already-installed, and error paths.
- Added regression tests in `tests/test_filters_build.py` for successful install summaries, already-installed output, and grouped install errors.
- Findings:
- PTK no longer routes `cargo install` through the generic cargo build formatter.
- The fix is intentionally scoped to install behavior; `cargo nextest` remains the next unresolved Cargo-specific discrepancy.
- Follow-up:
- Remove `CARGO-06` from the fix queue. Keep `CARGO-07` open.

### 2026-04-05 codex
- Reviewed IDs: JS-08, JS-09, JS-11, JS-12, JS-13, TOML-PKG-02, TOML-PKG-06
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/js/prisma_cmd.rs`, `rtk/src/cmds/js/pnpm_cmd.rs`, `rtk/src/cmds/js/npm_cmd.rs`, `rtk/src/filters/bundle-install.toml`, and `rtk/src/filters/uv-sync.toml` before editing.
- Updated `src/pytk_ai/plan/normalize.py` and `src/pytk_ai/data/rules.json` so PTK now routes `prisma migrate dev/status/deploy`, `prisma db push`, `pnpm outdated`, `pnpm install`, `npm run`/`npm exec`, `bundle update`, and `uv pip install` into the shared package filter path.
- Updated `src/pytk_ai/filters/packages.py` to add compact summaries for Prisma migrate/db-push flows, pnpm outdated/install, npm run boilerplate stripping, and `uv pip install`, while preserving the existing bundle and package-list behavior.
- Added regression coverage in `tests/test_filters_packages.py`, `tests/test_plan_normalize.py`, and `tests/test_plan_planner.py` for both filter output and end-to-end planning/routing.
- Findings:
- JS-08/09/11/12/13 were primarily routing gaps plus missing summarizers; PTK now has command-aware coverage for each reviewed flow without introducing a new filter module.
- TOML-PKG-02 was a real parity gap in PTK's own command detection rather than bundle summary logic; extending both hint inference and rules closed it.
- TOML-PKG-06 had a concrete PTK gap for `uv pip install`; PTK now matches the RTK TOML scope at the reviewed granularity.
- Follow-up:
- Remaining Prisma/package follow-up is limited to deeper parity details if RTK-specific formatting nuances matter beyond the compact summaries now covered here.

### 2026-04-05 codex
- Reviewed IDs: GH-05, CLD-06, CLD-07
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/git/gh_cmd.rs` and `rtk/src/cmds/cloud/container.rs` before editing: RTK handles `gh repo view` via forced JSON summarization, leaves `gh api` as explicit passthrough, and has dedicated compose log/build reducers.
- Updated `src/pytk_ai/plan/normalize.py` and `src/pytk_ai/data/rules.json` so PTK now routes broader `gh` commands plus `docker compose logs/build` into the existing GitHub and infra filter families while still skipping structured `gh --json/--jq/--template` flows.
- Updated `src/pytk_ai/filters/github_api.py` to add `gh.repo.view` handling, preserve `gh api` payloads, and keep non-targeted `gh` commands on a safe raw-output path inside the GH filter family.
- Updated `src/pytk_ai/filters/infra.py` to recognize `docker compose logs` and `docker compose build`, reuse log deduplication for compose logs, and summarize compose build headers, services, and step counts.
- Added regression coverage in `tests/test_filters_github_api.py`, `tests/test_filters_infra.py`, `tests/test_plan_normalize.py`, and `tests/test_plan_planner.py` for the new routing and summaries.
- Findings:
- GH-05 was primarily a PTK routing and mode-detection gap rather than a missing filter family; widening `gh` routing and adding focused repo/api behavior closed the reviewed RTK parity slice without introducing a new top-level filter.
- CLD-06 and CLD-07 are now command-aware in PTK and materially aligned with RTK's compose-specific handling, using PTK's existing infra/log style for the smallest correct implementation.
- Follow-up:
- Secondary GH rows (`GH-01` through `GH-04`) remain review-only items; this batch did not newly audit their deeper formatting parity beyond preserving their existing behavior.

### 2026-04-05 codex
- Reviewed IDs: GIT-01, GIT-02, GIT-03, GIT-04, GIT-05, GIT-06, GIT-07, GIT-08, GIT-09, GIT-10, GIT-11, GIT-12, GH-01, GH-02, GH-03, GH-04, DIFF-01, CARGO-01, CARGO-02, CARGO-03, JS-01, JS-02, JS-03, PY-01, PY-03, PY-04, PY-05, PY-06, GO-01, GO-02, GO-03, GO-04, RB-02, RB-03, CLD-01, CLD-02, CLD-03, CLD-04, CLD-05, CLD-08, CLD-09, CLD-10, CLD-11, CLD-12, SYS-01, SYS-02, SYS-05, SYS-06, SYS-11, TOML-BLD-03, TOML-INF-10
- Result: Conforms / Discrepant / Known scope gap
- Evidence:
- `rtk/src/cmds/git/git.rs` does more than pure text cleanup for several git rows: bare `git status` is re-run as `status --porcelain -b`; `git log` injects default `--pretty`, `-10`, and `--no-merges`; `git diff` and `git show` run extra `--stat`/summary passes; `git add` inspects cached diff stats after success; and `git branch`, `git stash`, and `git worktree` split read/list behavior from mutating subcommands.
- `src/pytk_ai/filters/git.py` only summarizes the command output it receives. It does not add RTK's extra execution passes or mode-specific command rewrites, though its success-path summaries for `commit`, `push`, `pull`, and `fetch` materially match RTK's compact outputs.
- `rtk/src/cmds/git/gh_cmd.rs` forces JSON for `gh pr list`, `pr view`, `issue list`, and `run list`; `src/pytk_ai/filters/github_api.py` now covers repo/api routing but still summarizes rendered CLI table/markdown output for those rows rather than RTK's structured fields.
- `rtk/src/cmds/git/diff_cmd.rs` supports both file-to-file comparison and unified-diff stdin condensation; `src/pytk_ai/filters/files.py` only condenses unified diff text.
- `rtk/src/cmds/rust/cargo_cmd.rs` reuses `filter_cargo_build()` for `cargo build`/`check`, has a dedicated `filter_cargo_clippy()`, and no current dedicated `cargo fmt` runner despite the RTK inventory row. PTK conforms for build, is narrower for clippy, and the `cargo fmt` row is an RTK inventory/code mismatch rather than a PTK bug.
- `rtk/src/cmds/js/lint_cmd.rs`, `tsc_cmd.rs`, and `next_cmd.rs` show that PTK materially matches TSC and Next.js, while Biome remains narrower because PTK lacks RTK's broader lint-wrapper and fallback behavior.
- `rtk/src/cmds/python/ruff_cmd.rs`, `pytest_cmd.rs`, `mypy_cmd.rs`, and `pip_cmd.rs` confirm PTK already matches the reviewed check/failure/list/outdated behaviors, with Ruff formatter scope already tracked separately in `PY-02`.
- `rtk/src/cmds/go/go_cmd.rs` and `golangci_cmd.rs` show RTK forces structured `go test -json` and `golangci-lint` JSON parsing, including v2 source-line support. PTK's `go test`/`build`/`vet` outputs are materially aligned, but `golangci-lint` remains narrower because PTK parses text only.

### 2026-04-05 codex
- Reviewed IDs: JS-05, JS-06, RB-01
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/js/playwright_cmd.rs`, `rtk/src/cmds/js/vitest_cmd.rs`, and `rtk/src/cmds/ruby/rake_cmd.rs` before editing to confirm RTK's JSON-first Playwright/Vitest parsing and text-driven Minitest reduction for `rake test` / `rails test`.
- Updated `src/pytk_ai/filters/__init__.py` and `src/pytk_ai/plan/normalize.py` so PTK now recognizes and dispatches `playwright`, `vitest`, and `rake` as real filter families instead of generic fallback targets.
- Updated `src/pytk_ai/filters/tests.py` to add Playwright and Vitest reducers that parse structured JSON payloads when available, preserve compact failure details, and retain reviewed text-summary fallback behavior for non-JSON output.
- Updated `src/pytk_ai/filters/ruby.py` to add a dedicated `rake`/Rails Minitest reducer that keeps the summary line plus bounded failure/error blocks and strips progress noise.
- Added regression coverage in `tests/test_filters_tests.py`, `tests/test_filters_ruby.py`, `tests/test_plan_normalize.py`, and `tests/test_plan_planner.py` for routing, wrapper planning, JSON-backed summaries, text fallback behavior, and Minitest parsing.
- Findings:
- JS-05 and JS-06 were dead-end rewrite gaps rather than missing planner rules; registering real reducers behind the existing wrapper names closes the reviewed PTK slice without adding a larger new test framework.
- RB-01 is now command-aware in PTK for both `rake test` and `rails test`-style planned commands, with RTK-aligned bounded Minitest failure retention.
- Follow-up:
- Execution-layer JSON coercion for Playwright/Vitest is still not owned in PTK the way RTK does it, but the new reducers safely handle both structured and text output so the audited filter-family gap is closed.

### 2026-04-05 codex
- Reviewed IDs: RUNNER-02
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/rust/runner.rs` before editing: RTK exposes a dedicated `run_test()` wrapper that executes an arbitrary command string and applies failures-focused extraction rather than requiring the caller to already be on a first-class test-family path.
- Added `run_test_command()` in `src/pytk_ai/runner.py` plus a real `pytk-ai test` CLI subcommand in `src/pytk_ai/cli.py`, so PTK now owns an arbitrary-command failures-only wrapper surface instead of only exposing filter hints through planning rewrites.
- Updated `src/pytk_ai/filters/tests.py` so wrapped test commands reuse existing PTK reducers for pytest, go test, rspec, and cargo test when recognizable, while preserving the existing generic failures-only reducer for other test runners.
- Added regression coverage in `tests/test_filters_tests.py`, `tests/test_runner.py`, and `tests/test_cli_run.py` for wrapped-command reducer reuse and the new CLI/runner wrapper surface.
- Findings:
- RUNNER-02 was a real surface gap, not just a missing alias: PTK had some test-family reducers, but no PTK-owned wrapper that executed arbitrary test commands and then applied those reducers.
- The new wrapper stays scoped to failures-only test handling and does not introduce the broader non-test errors-only wrapper tracked separately in `RUNNER-01`.
- Follow-up:
- Secondary parity work, if needed later, is limited to deeper per-framework formatting nuances inside the existing reducers rather than wrapper absence.
- `rtk/src/cmds/ruby/rspec_cmd.rs` and `rubocop_cmd.rs` inject JSON by default and keep richer structured metadata than PTK's text-only reducers in `src/pytk_ai/filters/ruby.py`.

### 2026-04-05 codex
- Reviewed IDs: GH-01, GH-02, GH-03, GH-04
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/git/gh_cmd.rs` before editing: RTK forces JSON execution for default `gh pr list`, `gh pr view`, `gh issue list`, and `gh run list`, keeps explicit structured-output requests raw, preserves `gh pr view --web/--comments` passthrough, and applies a default `--limit 10` for `gh run list`.
- Updated `src/pytk_ai/plan/execution_rewrites.py` so PTK now rewrites those four default GH flows to RTK-style `gh ... --json ...` execution, including identifier-aware `pr view` handling and passthrough for the special `pr view` modes.
- Updated `src/pytk_ai/filters/github_api.py` so PTK now summarizes the forced JSON payloads into RTK-aligned PR, issue, and workflow-run summaries while keeping the existing text fallback for passthrough and non-JSON paths.
- Added regression coverage in `tests/test_plan_execution_rewrites.py`, `tests/test_plan_planner.py`, and `tests/test_filters_github_api.py` for execution rewrites, planner-visible execution commands, JSON-backed summaries, and `pr view --comments` fallback behavior.
- Findings:
- GH-01 through GH-04 were primarily missing RTK's execution-layer JSON coercion; once PTK executed the same structured GH commands, the remaining parity work fit cleanly inside the existing GitHub filter.
- The fix stays scoped to the four audited rows and does not widen behavior for unrelated GH surfaces that were already reviewed separately.
- Follow-up:
- Secondary GH parity differences, if any remain, are outside this batch and should be handled in their own targeted review rather than widening this change set.
- `rtk/src/cmds/cloud/aws_cmd.rs`, `container.rs`, `curl_cmd.rs`, and `wget_cmd.rs` materially align with PTK's AWS/docker/kubectl/curl/wget summaries for the reviewed rows.
- `rtk/src/cmds/system/ls.rs`, `tree.rs`, `grep_cmd.rs`, `find_cmd.rs`, and `wc_cmd.rs` show PTK is materially aligned for `ls`, `tree`, `grep`, and `wc`, but narrower for `find` because RTK owns the traversal/parsing rather than summarizing raw shell output.
- `rtk/src/filters/biome.toml` strips check/fix/help noise and falls back to `biome: ok`, which PTK cannot reproduce without a TOML fallback layer; `rtk/src/filters/terraform-plan.toml` matches PTK's existing Terraform plan noise-stripping closely.
- Findings:
- New real PTK gaps cluster around RTK command wrappers that alter execution before filtering: `git status/log/diff/show/add/branch/stash/worktree`, the structured GH list/view rows, standalone `diff`, clippy-specific grouping, structured `golangci-lint`, JSON-first `rspec`/`rubocop`, RTK-owned `find`, and TOML-level Biome fallback behavior.
- Conforming rows in this batch are mostly the ones where RTK and PTK both operate on the same command surface and summarize similar raw/structured outputs without extra RTK-only command rewrites.
- `CARGO-03` is best treated as a source-of-truth mismatch note for the review board: the RTK inventory still claims a `cargo fmt` counterpart in `cargo_cmd.rs`, but the current RTK code appears to leave `cargo fmt` in passthrough handling.
- Follow-up:
- Add fix-queue entries for the newly reviewed git wrapper gaps, structured GH rows, standalone diff mode, clippy-specific grouping, structured golangci-lint, richer Ruby structured parsing, RTK-style find handling, and TOML-level Biome parity.

### 2026-04-05 codex
- Reviewed IDs: CARGO-07, PY-02, JS-14, TOML-BLD-03
- Result: Fixed / Improved
- Evidence:
- Re-read `rtk/src/cmds/rust/cargo_cmd.rs`, `rtk/src/cmds/python/ruff_cmd.rs`, and `rtk/src/cmds/system/format_cmd.rs` before editing to confirm RTK's nextest parser, Ruff formatter reducer, and formatter-dispatch behavior.
- Updated `src/pytk_ai/filters/build.py` so PTK now parses `cargo nextest` runs separately from cargo build output, stripping compile noise and summarizing failures, binaries, skips, cancellations, and pass-only summaries.
- Updated `src/pytk_ai/filters/python.py` so PTK now detects Ruff formatter check/write output and emits dedicated formatter summaries instead of routing those flows through the Ruff diagnostics parser or generic fallback.
- Added `src/pytk_ai/filters/formatters.py` plus routing updates in `src/pytk_ai/filters/__init__.py`, `src/pytk_ai/plan/normalize.py`, and `src/pytk_ai/data/rules.json` so PTK now has a bounded formatter slice for direct `prettier`, `black`, and `biome format` commands, including a `biome: ok` fallback for empty successful formatter output.
- Added regression coverage in `tests/test_filters_build.py`, `tests/test_filters_python.py`, `tests/test_plan_normalize.py`, and `tests/test_plan_planner.py` for nextest parsing, Ruff formatter summaries, and the new formatter-command routing.
- Findings:
- `CARGO-07` is now materially aligned with the reviewed RTK behavior because PTK no longer routes `cargo nextest` through cargo build diagnostics.
- `PY-02` is now closed because PTK has a distinct Ruff formatter path for both check and write mode output.
- `JS-14` improved substantially but remains only partial: PTK now handles explicit formatter commands, but it still does not provide RTK's broader auto-detected `format` command surface.
- `TOML-BLD-03` improved through explicit `biome format` handling, but full parity still depends on a wider TOML fallback/filter engine for all Biome flows.
- Follow-up:
- Keep `JS-14` and `TOML-BLD-03` in the fix queue for broader formatter-dispatch and TOML-fallback parity; remove `CARGO-07` and `PY-02` from active follow-up.

### 2026-04-05 codex
- Reviewed IDs: GT-01, GT-02, GT-03, GT-04, GT-05, GT-06, RUNNER-01, RUNNER-02, JS-04, JS-05, JS-06, RB-01, DN-01, DN-02, DN-03, DN-04, CLD-13, SYS-04, SYS-07, SYS-08, SYS-09, SYS-10, SYS-12
- Result: Missing / Known scope gap
- Evidence:
- `rtk/src/cmds/git/gt_cmd.rs` implements dedicated Graphite reducers for `gt log`, `submit`, `sync`, `restack`, and `create`, plus `run_other()` remapping selected `gt` subcommands to RTK git filters; PTK has no `gt` routing in `src/pytk_ai/plan/normalize.py`, no `gt` rule in `src/pytk_ai/data/rules.json`, and no `gt` filter registration in `src/pytk_ai/filters/__init__.py`.
- `rtk/src/cmds/rust/runner.rs` exposes wrapper-level `run_err()` and `run_test()` surfaces for arbitrary commands. PTK's `src/pytk_ai/runner.py` always executes the raw command and then dispatches only by inferred filter hint, so there is no wrapper equivalent for arbitrary errors-only or failures-only mode.
- `rtk/src/cmds/js/prettier_cmd.rs` is a dedicated Prettier reducer. PTK now routes direct `prettier` commands via `src/pytk_ai/plan/normalize.py` and `src/pytk_ai/data/rules.json` to `format.prettier` in `src/pytk_ai/filters/formatters.py`, but the Python formatter slice only covers a bounded subset of check-mode output and safe success cases.
- `rtk/src/cmds/js/playwright_cmd.rs` and `vitest_cmd.rs` both force structured test output and parse it into compact failure summaries. PTK `rules.json` rewrites Playwright and Vitest commands to `pytk-ai playwright` / `pytk-ai vitest`, but `src/pytk_ai/filters/__init__.py` has no registered `playwright` or `vitest` filters, so those commands fall back to the generic filter.
- `rtk/src/cmds/ruby/rake_cmd.rs` provides a Minitest reducer for `rake test` and `rails test`. PTK `rules.json` rewrites those commands to `pytk-ai rake`, but `src/pytk_ai/filters/__init__.py` has no `rake` filter implementation.
- `rtk/src/cmds/dotnet/dotnet_cmd.rs` implements build/test/restore/format handling with binlog, TRX, and format-report aware summaries. PTK `rules.json` contains only a `dotnet build` rewrite, with no `dotnet` filter registration in `src/pytk_ai/filters/__init__.py` and no corresponding Python filter module.
- `rtk/src/cmds/cloud/psql_cmd.rs` provides compact table and expanded-display formatting. PTK `rules.json` rewrites `psql`, but `src/pytk_ai/filters/__init__.py` has no `psql` filter registration.
- `rtk/src/cmds/system/json_cmd.rs`, `log_cmd.rs`, `env_cmd.rs`, `deps.rs`, `summary.rs`, and `local_llm.rs` define dedicated RTK utility surfaces. PTK has overlapping generic primitives in `src/pytk_ai/filters/base.py` and opportunistic JSON handling in non-system filters, but no dedicated command-aware counterparts for these system utilities.
- Findings:
- `GT-01` through `GT-06` are truly missing in PTK, not just narrower: there is no Graphite command family at all.
- `RUNNER-01` is truly missing; `RUNNER-02` remains partial because PTK has supported test-family reducers but no RTK-style failures-only wrapper surface.
- `JS-04` was stale on the board: PTK does have explicit `prettier` routing and a dedicated `format.prettier` reducer now, so this row is a known scope gap rather than a total absence.
- `JS-05`, `JS-06`, `RB-01`, `DN-01`, and `CLD-13` are still real PTK gaps even where `rules.json` already contains rewrites, because those rewrites currently target unimplemented filter families and degrade to generic output.
- `SYS-04`, `SYS-07`, `SYS-08`, `SYS-09`, `SYS-10`, and `SYS-12` remain truly missing as first-class PTK command surfaces; generic cleanup overlaps are too small to count as command-aware coverage.
- Follow-up:
- Add explicit fix-queue entries for Graphite, wrapper modes, missing JS test filters, Rake/Rails Minitest, `.NET`, `psql`, and the missing system utility surfaces; update formatter follow-up to reflect that direct Prettier coverage now exists but is still narrower than RTK.

### 2026-04-05 codex
- Reviewed IDs: JS-01, JS-04, JS-14, TOML-BLD-03
- Result: Fixed / Improved
- Evidence:
- Re-read `rtk/src/cmds/js/lint_cmd.rs`, `rtk/src/cmds/js/prettier_cmd.rs`, `rtk/src/cmds/system/format_cmd.rs`, and `rtk/src/filters/biome.toml` before editing to confirm RTK's wrapper-aware JS linting, Prettier check/write reduction, formatter dispatch boundaries, and TOML-level Biome cleanup behavior.
- Updated `src/pytk_ai/plan/normalize.py` and `src/pytk_ai/data/rules.json` so PTK now recognizes wrapper-prefixed `prettier` and `biome` commands (`pnpm exec`, `npm exec`, `yarn`, `bunx`) and routes write-style `biome check` flows through the formatter path instead of generic lint handling.
- Updated `src/pytk_ai/filters/formatters.py` so PTK now distinguishes Prettier check vs write output, summarizes formatted-file lists, and expands Biome formatter cleanup to strip RTK-like noise lines and preserve `biome: ok` clean-success behavior.
- Updated `src/pytk_ai/filters/build.py` so PTK's Biome lint path now strips the `biome.toml` noise lines, keeps grouped one-line diagnostics when available, and otherwise preserves the meaningful Biome diagnostic block plus summary instead of falling through to generic output.
- Added regression coverage in `tests/test_filters_build.py`, `tests/test_plan_normalize.py`, and `tests/test_plan_planner.py` for wrapper-prefixed formatter/linter routing, Prettier write-mode summaries, Biome block diagnostics, and write-style `biome check` planning.
- Findings:
- `JS-01` is now closed at the reviewed granularity: PTK keeps ESLint grouping, broadens JS wrapper coverage, and gives Biome check/lint output a command-aware reduction instead of only a narrow text parse.
- `JS-04` is now closed at the reviewed granularity because PTK's Prettier reducer covers both files-needing-formatting and files-formatted flows rather than only the earlier bounded check-only slice.
- `JS-14` improved but remains partial because PTK still lacks RTK's broader auto-detected `format` surface; this batch only strengthened the explicit formatter-command slice.
- `TOML-BLD-03` improved materially through RTK-like Biome noise stripping and `biome: ok` fallback across more Biome-owned flows, but it remains open because PTK still lacks RTK's declarative TOML fallback engine for the wider command family.
- Follow-up:
- Keep `JS-14` and `TOML-BLD-03` in the fix queue. Remove `JS-04` from active formatter follow-up; future JS formatter work should focus on the higher-level `format` surface rather than direct Prettier parsing.

### 2026-04-05 codex
- Reviewed IDs: DIFF-01, SYS-06, SYS-03
- Result: Fixed / Reassessed
- Evidence:
- Re-read `rtk/src/cmds/git/diff_cmd.rs`, `rtk/src/cmds/system/find_cmd.rs`, and `rtk/src/cmds/system/read.rs` before editing to confirm RTK's direct file-compare diff path, command-owned find traversal, and richer dedicated read surface.
- Updated `src/pytk_ai/plan/execution_rewrites.py` so PTK now rewrites plain two-path `diff` calls to unified diff execution and rewrites supported `find` invocations into a Python walker with RTK-like handling for `-name`/`-iname`, `-type`, `-maxdepth`, and ignore-style pruning.
- Updated `src/pytk_ai/filters/files.py` so PTK now formats direct file-to-file diff comparisons with RTK-style add/remove headers, keeps unified-diff condensation for explicit patch output, and emits grouped RTK-style `find` summaries with extension counts.
- Added regression coverage in `tests/test_filters_files.py`, `tests/test_plan_normalize.py`, `tests/test_plan_planner.py`, and `tests/test_live_system.py` for planner-visible rewrites, file diff summaries, and live `find`/`diff` execution.
- Findings:
- `DIFF-01` is now materially closed for the audited PTK surface: PTK handles both direct two-file `diff` commands and preexisting unified diff text.
- `SYS-06` is now materially closed for the audited RTK slice without implementing the full RTK CLI syntax; PTK owns traversal and grouping for supported native `find` forms rather than merely compacting raw output.
- `SYS-03` remains a real scope gap. These changes do not add RTK's dedicated `read` command semantics such as filter levels, stdin mode, structural truncation, or optional line numbering.
- Follow-up:
- Keep `SYS-03` tied to the broader read-surface work in `CORE-02..05`; unsupported/compound `find` predicates remain intentionally out of scope for this batch.

### 2026-04-05 codex
- Reviewed IDs: CORE-01, CORE-02, CORE-05, SYS-03
- Result: Fixed / Improved
- Evidence:
- Re-read `rtk/src/core/filter.rs`, `rtk/src/cmds/system/read.rs`, and `rtk/src/core/toml_filter.rs` before editing to confirm RTK's read CLI contract, filter levels, structural truncation, and the separate TOML fallback engine scope.
- Updated `src/pytk_ai/cli.py` to add a real `pytk-ai read` subcommand with `--level`, `--max-lines`, `--tail-lines`, `--line-numbers`, and stdin (`-`) support.
- Updated `src/pytk_ai/filters/files.py` so PTK now owns shared read rendering with RTK-style none/minimal/aggressive levels, line numbering, tail/max-line windowing, and structure-aware truncation for `read` output.
- Updated `src/pytk_ai/subprocess_utils.py` so repo-local planned `pytk-ai ...` commands execute via `python3 -m pytk_ai` with the workspace `src/` path, making the new first-class read surface actually runnable in this checkout.
- Added regression coverage in `tests/test_filters_files.py`, `tests/test_plan_normalize.py`, and `tests/test_live_system.py` for read-level filtering, line numbering, structural truncation, and live `pytk-ai read` execution.
- Findings:
- `CORE-02` and `SYS-03` are now materially closed: PTK no longer only hints at a read surface in planning; it now executes and formats a dedicated `read` command with the audited RTK behaviors.
- `CORE-05` is closed at the reviewed granularity because PTK now applies structure-aware truncation on the owned `read` path instead of only generic output line caps.
- `CORE-01` improved only indirectly through stronger PTK-owned fallback/read shaping, but RTK's declarative TOML registry and ordered fallback pipeline remain a distinct architectural gap.
- Follow-up:
- Keep `CORE-01` open for a future declarative fallback engine. `CORE-03` and `CORE-04` remain separate read-filter depth gaps beyond this batch's scope.

### 2026-04-05 codex
- Reviewed IDs: JS-14, TOML-BLD-03
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/system/format_cmd.rs` and `rtk/src/filters/biome.toml` before editing to confirm RTK's explicit-or-auto-detected `format` wrapper behavior and the actual audited Biome TOML slice (`^biome\b` noise stripping plus `on_empty = "biome: ok"`).
- Updated `src/pytk_ai/runner.py` and `src/pytk_ai/cli.py` so PTK now exposes a real `pytk-ai format` wrapper surface that auto-detects `prettier`, `black`, `ruff`, or `biome` from explicit args or project files, applies the same small default-flag conventions as RTK (`black --check`, `ruff format`, default `.` target), executes the detected formatter, and reuses the existing formatter-specific reducers by passing a formatter-aware command into filtering.
- Added regression coverage in `tests/test_runner.py` and `tests/test_cli_run.py` for explicit `prettier` wrapper execution, auto-detected `ruff` execution from `pyproject.toml`, and the new CLI subcommand surface.
- Reassessed PTK's existing Biome cleanup against `rtk/src/filters/biome.toml`: `src/pytk_ai/filters/build.py` and `src/pytk_ai/filters/formatters.py` already strip the same checked/fixed/helper noise lines, preserve diagnostic blocks, and emit `biome: ok` on clean empty success across lint and formatter flows.
- Findings:
- `JS-14` is now materially closed at the reviewed RTK granularity because PTK has the missing formatter wrapper surface rather than only direct-command routing.
- `TOML-BLD-03` is also closed honestly: despite PTK still lacking RTK's general TOML fallback engine, the specific built-in `biome.toml` behavior audited for this row is now covered command-aware.
- Follow-up:
- Keep `CORE-01` open as the remaining general TOML/declarative fallback-engine gap; no separate follow-up remains for `JS-14` or `TOML-BLD-03`.

### 2026-04-05 codex
- Reviewed IDs: DN-01, DN-02, DN-03, DN-04
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/dotnet/dotnet_cmd.rs` before editing to confirm the reviewed RTK slice: compact summaries for `dotnet build`, `test`, `restore`, and `format`, plus a dedicated wrapper-owned command surface.
- Added `src/pytk_ai/filters/dotnet.py` and registered it in `src/pytk_ai/filters/__init__.py`, giving PTK a real `.NET` filter family for build/test/restore/format text output rather than a dead-end rewrite.
- Updated `src/pytk_ai/plan/normalize.py`, `src/pytk_ai/data/rules.json`, `src/pytk_ai/runner.py`, and `src/pytk_ai/cli.py` so PTK now recognizes the full `.NET` family and exposes a real `pytk-ai dotnet` wrapper surface.
- Added regression coverage in `tests/test_filters_dotnet.py`, `tests/test_plan_normalize.py`, `tests/test_plan_planner.py`, `tests/test_runner.py`, and `tests/test_cli_run.py`; targeted tests and `ruff` passed.
- Findings:
- PTK now closes the practical `.NET` gap by backing the existing rewrite with a dedicated filter family and wrapper surface rather than only planner metadata.
- The PTK implementation is intentionally text-first and does not attempt RTK's full binlog/TRX/report parsing architecture, but it materially covers the reviewed output-shaping slice for the audited rows.
- Follow-up:
- Remove `DN-01..04` from the fix queue. Any future `.NET` work is deeper parity, not missing-surface coverage.

### 2026-04-05 codex
- Reviewed IDs: GT-01, GT-02, GT-03, GT-04, GT-05, GT-06
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/git/gt_cmd.rs` before editing to confirm the reviewed RTK slice: dedicated Graphite reducers for `log`, `submit`, `sync`, `restack`, `create`, identity handling for `branch`, and passthrough-to-git remap for git-like `gt` subcommands.
- Added `src/pytk_ai/filters/gt.py` and registered it in `src/pytk_ai/filters/__init__.py`, giving PTK a real Graphite filter family for the audited stack workflows.
- Updated `src/pytk_ai/plan/normalize.py`, `src/pytk_ai/data/rules.json`, `src/pytk_ai/runner.py`, and `src/pytk_ai/cli.py` so PTK now recognizes `gt`, exposes a real `pytk-ai gt` wrapper surface, and remaps git-like Graphite passthrough commands to existing PTK git reducers.
- Added regression coverage in `tests/test_filters_gt.py`, `tests/test_plan_normalize.py`, `tests/test_plan_planner.py`, `tests/test_runner.py`, and `tests/test_cli_run.py`; targeted tests and `ruff` passed.
- Findings:
- PTK now closes the practical Graphite missing-surface gap with a dedicated wrapper and filter family rather than only planner metadata.
- The PTK implementation is intentionally text-first and scoped to the reviewed RTK Graphite slice; deeper parity beyond these audited reducers is follow-up work, not a remaining missing surface.
- Follow-up:
- Remove `GT-01..06` from the fix queue. Any future Graphite work is deeper formatting parity rather than absent command-aware coverage.

### 2026-04-05 codex
- Reviewed IDs: SYS-04, SYS-07, SYS-08, SYS-09, SYS-10, SYS-12
- Result: Fixed
- Evidence:
- Re-read `rtk/src/cmds/system/json_cmd.rs`, `log_cmd.rs`, `env_cmd.rs`, `deps.rs`, `summary.rs`, and `local_llm.rs` before editing to confirm the reviewed RTK slice: PTK-owned wrapper surfaces rather than planner rewrites for these utilities.
- Added `src/pytk_ai/filters/system_tools.py` with PTK-owned implementations for compact/schema JSON rendering, log normalization and deduplication, environment masking/grouping, dependency manifest summaries, heuristic arbitrary-command summaries, and two-line heuristic file summaries.
- Updated `src/pytk_ai/runner.py` and `src/pytk_ai/cli.py` so PTK now exposes real `pytk-ai json`, `log`, `env`, `deps`, `summary`, and `smart` surfaces.
- Added regression coverage in `tests/test_filters_system_tools.py`, `tests/test_runner.py`, and `tests/test_cli_run.py`; targeted tests and `ruff` passed.
- Findings:
- PTK now closes the remaining missing-surface system-utility batch with wrapper-owned library logic, matching the reviewed RTK command ownership model.
- The PTK implementations are intentionally minimal and text-first, but materially cover the audited rows without introducing the broader architectural work that belongs to `CORE-01`, `CORE-03`, or `CORE-04`.
- Follow-up:
- Remove `SYS-04,07..10,12` from the fix queue. Remaining open work is now the deeper core filtering gaps rather than missing wrapper surfaces.

### 2026-04-06 codex
- Reviewed IDs: CORE-01
- Result: Improved
- Evidence:
- Re-read `rtk/src/core/toml_filter.rs`, `rtk/build.rs`, and representative built-ins such as `rtk/src/filters/make.toml`, `rsync.toml`, `spring-boot.toml`, and `df.toml` before editing to verify RTK's actual built-in registry ordering and the eight-stage fallback pipeline: `strip_ansi`, chained `replace`, `match_output` with optional `unless`, line strip/keep, line truncation, head/tail omission markers, `max_lines`, and `on_empty`.
- Added `src/pytk_ai/filters/toml_fallback.py` and updated `src/pytk_ai/filters/generic.py` plus `src/pytk_ai/filters/__init__.py` so PTK's generic fallback path can now load RTK built-in filter definitions from the checked-out `rtk/src/filters/*.toml` files and apply the same ordered declarative transformation stages for commands that do not already route to a dedicated PTK filter.
- Added targeted regression coverage in `tests/test_filters_generic.py` for built-in fallback command matching (`make`), `match_output` plus `unless` (`rsync`), keep-lines filtering (`spring-boot`), and line truncation plus final line caps (`df`).
- Findings:
- PTK no longer lacks the declarative fallback pipeline entirely: it now has bounded parity for RTK's built-in command-matched fallback behavior on the generic path.
- `CORE-01` is not fully closed because this implementation is repo-backed and bounded: it does not yet provide a packaged built-in registry independent of the checked-out `rtk/` tree, and it still omits RTK's project-local and user-global TOML sources, trust gating, and broader registry-management semantics.
- Follow-up:
- Keep `CORE-01` open until PTK vendors the built-in fallback registry into its own package surface and decides whether project/global TOML sources are in scope for parity.

## Fix Queue

| ID | Gap Summary | Candidate PTK Area | Status |
| --- | --- | --- | --- |
| CORE-01 | Finish RTK-like declarative fallback support by vendoring the built-in registry into PTK packaging and deciding whether project/global TOML sources, trust gating, and debug semantics should be ported. | `src/pytk_ai/filters/generic.py`, `src/pytk_ai/filters/toml_fallback.py`, packaging/data surface | proposed |
| CORE-03 | Port or redesign RTK minimal/aggressive file-content filtering for PTK-owned read flows. | `src/pytk_ai/filters/files.py` or a new source-filter module | done |
| CARGO-02 | Split `cargo clippy` into a dedicated lint-rule-oriented summarizer instead of reusing the generic cargo build reducer. | `src/pytk_ai/filters/build.py` | done |
| JS-14 | Expand the stronger explicit formatter slice into fuller RTK parity: auto-detected `format` dispatch plus broader formatter command coverage beyond direct/wrapper-owned `prettier`, `black`, and Biome flows. | planning/CLI surface plus formatter filter module(s) | done |
| GO-04 | Add structured `golangci-lint` JSON handling, including v2 output support, instead of relying on text parsing. | `src/pytk_ai/filters/go.py`, planning/routing if needed | done |
| RB-02..03 | Add RTK-like structured JSON-first RSpec and RuboCop handling, including pending/correctable/autocorrect metadata. | `src/pytk_ai/filters/ruby.py`, planning/routing if needed | done |
| TOML-BLD-03 | Add Biome fallback parity through either TOML-style fallback filtering or equivalent command-aware cleanup for non-lint Biome flows. | fallback filter engine or lint/formatter routing | done |
| GT-01..06 | Add a PTK Graphite `gt` filter family for stack workflows plus RTK-style passthrough/remap handling for git-like `gt` subcommands. | planning/rules plus a new `src/pytk_ai/filters/gt.py` (or equivalent) | done |
| RUNNER-01..02 | Add wrapper-style PTK surfaces for arbitrary-command errors-only and failures-only reductions rather than relying only on per-command filters. | CLI/planning surface plus generic/test reducers | done |
| JS-05..06 | Add dedicated Playwright and Vitest structured test filters; current planning rewrites target unimplemented filter names and fall back to generic output. | planning/rules plus new JS test filter module(s) | done |
| RB-01 | Add a Rake / Rails Minitest filter instead of rewriting to an unimplemented `pytk-ai rake` surface. | planning/rules plus `src/pytk_ai/filters/ruby.py` or a new Ruby test filter module | done |
| DN-01..04 | Add a `.NET` filter family for `dotnet build`, `test`, `restore`, and `format`; the current inventory only contains a dead-end `dotnet build` rewrite with no backing filter. | planning/rules plus a new `src/pytk_ai/filters/dotnet.py` | done |
| CLD-13 | Wire `psql` to a dedicated compact table / expanded-record filter instead of the current dead-end rewrite. | planning/rules plus a new `src/pytk_ai/filters/psql.py` or infra extension | done |
| SYS-04,07..10,12 | Add first-class PTK system utility surfaces for JSON viewing, log deduplication, env masking, dependency summaries, heuristic command summaries, and local file summaries. | CLI/planning surface plus new system filter modules | done |
