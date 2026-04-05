# PYTK-AI Filters Inventory

This document summarizes every filter currently implemented under `src/pytk_ai/filters/`, how each one is selected, and the `filter_name` values it emits.

## Shared behavior

Most filters eventually pass their text through `make_filter_result()` from `src/pytk_ai/filters/base.py`. That shared layer:

- strips ANSI escape sequences
- normalizes carriage returns to newlines
- collapses long blank-line runs
- collapses repeated identical lines
- truncates long output to the configured maximum line count

`filter_output()` in `src/pytk_ai/filters/__init__.py` picks a filter from the top-level registry using a command `filter_hint`. If no specific filter matches, it falls back to `generic`.

## Top-level filter registry

These are the top-level filter hints registered in `src/pytk_ai/filters/__init__.py`:

| Filter hint | Handler | Purpose |
| --- | --- | --- |
| `aws` | `filter_infra_output` | AWS CLI summaries for read/list/describe style commands |
| `cargo` | `filter_cargo_output` | Rust build, clippy, and fmt summaries |
| `curl` | `filter_github_api_output` | API / HTTP response summarization |
| `diff` | `filter_file_output` | Unified diff summarization |
| `docker` | `filter_infra_output` | Docker and Docker Compose summaries |
| `find` | `filter_file_output` | Filesystem search summaries |
| `gh` | `filter_github_api_output` | GitHub CLI list/view summaries |
| `git` | `filter_git_output` | Git command summaries |
| `go` | `filter_go_output` | Go test/build/vet summaries |
| `golangci-lint` | `filter_golangci_output` | golangci-lint issue grouping |
| `grep` | `filter_file_output` | Search result grouping |
| `kubectl` | `filter_infra_output` | Kubernetes resource/log summaries |
| `lint` | `filter_lint_output` | ESLint / Biome summaries |
| `ls` | `filter_system_output` | Compact directory listing |
| `mypy` | `filter_python_output` | mypy diagnostics summary |
| `next` | `filter_next_output` | Next.js build summary |
| `package` | `filter_package_output` | Package manager summaries |
| `pytest` | `filter_python_output` | pytest failure summary |
| `read` | `filter_file_output` | raw file read helpers |
| `rspec` | `filter_rspec_output` | RSpec failure summary |
| `rubocop` | `filter_rubocop_output` | RuboCop offense summary |
| `ruff` | `filter_python_output` | Ruff issue summary |
| `test` | `filter_test_output` | generic test runner summary |
| `tree` | `filter_file_output` | tree output summary |
| `tsc` | `filter_tsc_output` | TypeScript compiler diagnostics |
| `terraform` | `filter_infra_output` | Terraform plan/validate summaries |
| `wc` | `filter_file_output` | word-count summaries |
| `wget` | `filter_github_api_output` | download result summary |

## Concrete filters and emitted `filter_name` values

### `generic.py`

- `generic`
  Brief behavior: combines `stdout` and `stderr`, preferring `stderr` first on failures, then applies only the shared cleanup/truncation pipeline.

### `git.py`

- `git`
  Brief behavior: fallback name when no git subcommand is detected.
- `git.status`
  Brief behavior: parses porcelain status, extracts branch/ahead/behind state, groups staged/modified/deleted/renamed/untracked/conflict paths, and compresses paths by directory.
- `git.log`
  Brief behavior: compacts verbose `git log` output into one line per commit with short hash, refs, and subject.
- `git.diff`
  Brief behavior: summarizes changed files with added/removed counts and a few sample changed lines.
- `git.show`
  Brief behavior: same diff summarizer as `git diff`, but prepends commit hash and subject when available.
- `git.add`
  Brief behavior: returns cleaned command output or `ok` for silent success.
- `git.commit`
  Brief behavior: extracts the committed short hash and subject, falling back to `ok`.
- `git.push`
  Brief behavior: reports `ok up-to-date` or the pushed ref target.
- `git.pull`
  Brief behavior: reports `ok up-to-date` or summarizes changed files / insertions / deletions.
- `git.branch`
  Brief behavior: keeps local branches compact and groups remote branches under a counted `remotes` section.
- `git.fetch`
  Brief behavior: counts updated refs and reports `ok fetched (N refs)`.
- `git.stash`
  Brief behavior: keeps the first stash result line or the top stash list entries.
- `git.worktree`
  Brief behavior: extracts branch, path, and short commit for each worktree.

Special note: git advice lines beginning with `(use "git ...` are removed before summarization.

### `python.py`

- `python`
  Brief behavior: generic fallback for Python-related commands when no specialized branch matches.
- `python.pytest`
  Brief behavior: extracts pytest failures and short test summary information, limiting the number of displayed failures.
- `python.ruff`
  Brief behavior: parses Ruff JSON or text output, counts issues and fixable items, then groups by top rules and top files.
- `python.mypy`
  Brief behavior: parses mypy diagnostics, groups errors by file, counts common error codes, and preserves associated notes.

### `system.py`

- `system`
  Brief behavior: generic fallback for system commands handled by this module.
- `system.ls`
  Brief behavior: parses long-form `ls` output, hides common noise directories unless `-a/-A/--all` is present, shows compact names and human-readable sizes, then appends a file/dir/symlink summary.
- `system.read.cat`
  Brief behavior: raw cleaned `cat` output without the higher-level summarizers.
- `system.read.head`
  Brief behavior: raw cleaned `head` output.
- `system.read.tail`
  Brief behavior: raw cleaned `tail` output with repeated identical lines collapsed aggressively.
- `system.grep`
  Brief behavior: naming branch only; actual grep/search summarization is mainly implemented in `files.py`.
- `system.find`
  Brief behavior: naming branch only; actual find summarization is mainly implemented in `files.py`.

### `files.py`

- `read`
  Brief behavior: raw read-output handler for the generic `read` command path when the command name is not literally `cat`, `head`, or `tail`.
- `system.read.cat`
  Brief behavior: used here as well for `cat`-style reads; strips ANSI and preserves mostly raw content.
- `system.read.head`
  Brief behavior: used here as well for `head`-style reads.
- `system.read.tail`
  Brief behavior: used here as well for `tail`-style reads, collapsing repeated identical lines.
- `search.grep`
  Brief behavior: groups `rg`/`grep` matches by file, counts total matches, and keeps a few sample matching lines per file. If grep exits `1` with no output, it returns `0 matches`.
- `search.find`
  Brief behavior: groups found paths by parent directory and shows a counted directory summary.
- `files.tree`
  Brief behavior: keeps the tree summary line with directory/file counts plus a short preview of entries.
- `files.wc`
  Brief behavior: parses `wc` columns using command flags, labels metrics such as lines/words/chars/bytes, and summarizes totals across files when present.
- `files.diff`
  Brief behavior: summarizes unified diff output by file, with added/removed counts and a few sample change lines.

### `build.py`

- `cargo.build`
  Brief behavior: parses Cargo compiler diagnostics, counts compiled crates, groups errors and warnings by file, and shows top diagnostic codes.
- `cargo.clippy`
  Brief behavior: same Cargo diagnostic summarizer, but named specifically for `cargo clippy`.
- `cargo.fmt`
  Brief behavior: reports formatting success or lists files that would be reformatted / have diffs.
- `lint.eslint`
  Brief behavior: parses stylish ESLint output, counts errors and warnings, groups by file, and lists top violated rules.
- `lint.biome`
  Brief behavior: parses Biome diagnostics, counts errors/warnings, groups by file, and lists top rules.
- `tsc`
  Brief behavior: parses `tsc` diagnostics, groups errors by file, counts TypeScript error codes, and keeps one context line when present.
- `next.build`
  Brief behavior: summarizes Next.js build output by route counts, static/dynamic split, largest first-load bundles, build time, warning count, and error count.

### `go.py`

- `go.test`
  Brief behavior: summarizes package-level pass/fail state, test failures, and build errors from `go test`.
- `go.build`
  Brief behavior: reports success or lists `.go:` build issues from `go build`.
- `go.vet`
  Brief behavior: reports clean output or lists `.go:` vet findings from `go vet`.
- `golangci-lint`
  Brief behavior: parses golangci-lint findings, counts issues by linter, and groups them by file.

### `ruby.py`

- `rubocop`
  Brief behavior: parses RuboCop offenses by file, lists offense counts, and shows line/cop/message samples; on clean runs it emits a compact `ok rubocop` summary.
- `rspec`
  Brief behavior: extracts RSpec failure sections, strips gem noise, keeps the example/failure summary, and shows a few compacted failures.

### `packages.py`

- `pip.list`
  Brief behavior: parses table or JSON package listings and shows package names/versions plus warning lines.
- `pip.outdated`
  Brief behavior: parses outdated package tables or JSON and shows current-to-latest upgrades.
- `uv.sync`
  Brief behavior: summarizes `uv sync` package additions/removals/updates, detects already-up-to-date runs, and keeps warnings.
- `npm.list`
  Brief behavior: parses text tree output or JSON dependency graphs and lists discovered dependencies compactly.
- `pnpm.list`
  Brief behavior: same dependency-list summarizer as `npm.list`, adapted to pnpm command detection.
- `bundle.install`
  Brief behavior: summarizes Bundler installs with installed/fetched gems and warning lines.
- `bundle.update`
  Brief behavior: same Bundler summarizer, but named for update flows.
- `prisma.generate`
  Brief behavior: detects Prisma client generation, extracts model/enum/type counts when present, and reports the generated target package/path.

### `infra.py`

- `infra`
  Brief behavior: generic fallback name when an infra command is routed here but no specific kind is recognized.
- `docker.ps`
  Brief behavior: parses container tables, shows container id/name/image/status, and compacts exposed ports.
- `docker.images`
  Brief behavior: parses image tables, totals image sizes where possible, and shows a short list of images and sizes.
- `docker.logs`
  Brief behavior: keeps mostly raw logs, but strips ANSI and collapses repeated lines; prefixes the selected container target when found.
- `docker.compose.ps`
  Brief behavior: summarizes compose services with image, status, and compact ports.
- `kubectl.pods`
  Brief behavior: parses JSON or table output, counts running/pending/failed pods and restarts, and highlights problematic pods.
- `kubectl.services`
  Brief behavior: parses JSON or table output and lists services with namespace, type, and exposed ports.
- `kubectl.logs`
  Brief behavior: keeps mostly raw pod logs with repeated-line collapsing and a prefixed target label.
- `aws.read`
  Brief behavior: summarizes common AWS read/list/describe JSON responses, including special handling for STS identity, EC2 instances, S3 listings, and several common collection payloads.
- `terraform.plan`
  Brief behavior: removes Terraform lock/refresh/noise lines and preserves the meaningful plan summary, including `no changes` detection.
- `terraform.validate`
  Brief behavior: compacts validate success into `terraform validate: ok (valid)` and otherwise returns cleaned validation output.

### `github_api.py`

- `gh`
  Brief behavior: generic fallback for GitHub CLI commands routed here when no specialized mode is matched.
- `gh.pr.list`
  Brief behavior: normalizes `gh pr list` tabular output into compact rows and counts pull requests.
- `gh.pr.view`
  Brief behavior: cleans markdown-heavy PR output by stripping comments/badges/rules, keeps the PR title and header lines, then includes a trimmed body preview.
- `gh.issue.list`
  Brief behavior: normalizes `gh issue list` rows and counts issues.
- `gh.run.list`
  Brief behavior: normalizes `gh run list` rows and counts workflow runs.
- `curl`
  Brief behavior: summarizes JSON API responses as a compact schema preview when shorter than the raw payload; otherwise preserves a shortened textual response. Download-mode curl is left mostly raw.
- `wget`
  Brief behavior: summarizes download success as `url ok | filename | size`, or reports compact failure reasons such as 404, DNS, timeout, or SSL errors.

### `tests.py`

- `test.cargo`
  Brief behavior: generic test summarizer with special emphasis on retaining Rust `test result:` lines.
- `test.generic`
  Brief behavior: extracts summary lines and failure blocks from generic test tool output, then falls back to the last meaningful lines if no formal summary is found.

## Filter policy mapping

`src/pytk_ai/filters/policy.py` assigns a `FilterPolicy` to final `filter_name` values:

- `success-only`
  Applied to filters that mainly summarize successful output while preserving failures more directly, such as `curl`, `docker.*`, `gh.*`, `pip.*`, `search.*`, `system.ls`, `terraform.plan`, `uv.sync`, and `wget`.
- `both`
  Applied to filters that summarize both success and failure paths, such as `aws.read`, `cargo.*`, `git.log`, `git.diff`, `go.*`, `lint.*`, `next.build`, `python.*`, `rspec`, `rubocop`, and `test.*`.
- `failure-only`
  Reserved in code for `reserved.failure-only`, but no active filter currently emits that name.

## Notes

- Some modules expose helper/fallback names that are not top-level registry hints but still appear in results, for example `cargo.fmt`, `bundle.update`, `docker.compose.ps`, and `gh.pr.view`.
- `system.py` contains naming branches for `grep` and `find`, but the main registry currently routes `grep` and `find` through `files.py`, where the actual summarization for search-style output lives.
