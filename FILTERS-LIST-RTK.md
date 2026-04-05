# RTK Filter Inventory

This file inventories the filters implemented in `/rtk`, grouped by how RTK applies them.

## How RTK Chooses a Filter

- `rtk/src/main.rs`
  Routes known `rtk ...` subcommands to dedicated Rust filter modules in `src/cmds/**`. If Clap cannot parse a subcommand, RTK falls back to TOML filter lookup.
- `rtk/src/discover/rules.rs`
  Holds the rewrite rules that map raw shell commands to RTK entrypoints.
- `rtk/src/core/toml_filter.rs`
  Loads project, user, and built-in TOML filters, then applies the declarative fallback pipeline.
- `rtk/build.rs`
  Concatenates all built-in `src/filters/*.toml` files into one embedded TOML bundle at build time.
- `rtk/src/core/runner.rs`
  Shared execution harness for Rust filters: runs the command, applies the filter function, preserves exit codes, and tracks savings.

## Core Filter Engines

### TOML output filter pipeline

Implemented in `rtk/src/core/toml_filter.rs`.

Applied stages, in order:

1. `strip_ansi` removes ANSI control sequences.
2. `replace` applies chained regex substitutions line by line.
3. `match_output` can short-circuit the whole output to a fixed message.
4. `strip_lines_matching` or `keep_lines_matching` removes or preserves lines by regex.
5. `truncate_lines_at` shortens long lines.
6. `head_lines` and `tail_lines` keep only the beginning/end, inserting omission markers.
7. `max_lines` enforces a final line cap.
8. `on_empty` emits a fallback message if nothing remains.

### File-content filters

Implemented in `rtk/src/core/filter.rs` and used by `rtk read` / `rtk smart`.

- `FilterLevel::None`
  No filtering; returns raw file content.
- `MinimalFilter`
  Removes comments and excess blank lines while preserving most code structure.
- `AggressiveFilter`
  Keeps imports, signatures, declarations, and structure while eliding most implementation bodies.
- `smart_truncate()`
  Truncates long files while trying to keep signatures and important structural lines.

## Rust Command Filters

These are the dedicated programmatic filters under `rtk/src/cmds/**`.

### Git and VCS

- `rtk/src/cmds/git/git.rs`
  Filters `git status`, `log`, `diff`, `show`, `add`, `commit`, `push`, `pull`, `branch`, `fetch`, `stash`, and `worktree` into compact summaries.
- `rtk/src/cmds/git/gh_cmd.rs`
  Filters `gh` output, often by forcing JSON and summarizing PRs, issues, runs, repos, and API results.
- `rtk/src/cmds/git/gt_cmd.rs`
  Filters Graphite `gt` stack workflows like `log`, `submit`, `sync`, `restack`, `create`, and `branch` into concise stack summaries.
- `rtk/src/cmds/git/diff_cmd.rs`
  Standalone diff condenser that keeps only meaningful changed lines.

### Rust

- `rtk/src/cmds/rust/cargo_cmd.rs`
  Filters `cargo build`, `test`, `clippy`, `check`, `install`, and `nextest` by stripping compile noise and keeping diagnostics and test failures.
- `rtk/src/cmds/rust/runner.rs`
  Provides generic reducers like errors-only and failures-only output modes.

### JavaScript and TypeScript

- `rtk/src/cmds/js/lint_cmd.rs`
  Groups lint diagnostics by file and rule; can force structured output for supported linters.
- `rtk/src/cmds/js/tsc_cmd.rs`
  Groups TypeScript compiler errors by file and error code.
- `rtk/src/cmds/js/next_cmd.rs`
  Reduces `next build` output to route and bundle summaries.
- `rtk/src/cmds/js/prettier_cmd.rs`
  Shows only files needing formatting or changed by formatting.
- `rtk/src/cmds/js/playwright_cmd.rs`
  Forces structured test output and keeps failures plus a compact summary.
- `rtk/src/cmds/js/vitest_cmd.rs`
  Forces structured test output and keeps failures plus a compact summary.
- `rtk/src/cmds/js/prisma_cmd.rs`
  Removes Prisma ASCII art and reduces generate, migrate, and db push output to concise summaries.
- `rtk/src/cmds/js/pnpm_cmd.rs`
  Compresses `pnpm list`, `outdated`, and `install` output.
- `rtk/src/cmds/js/npm_cmd.rs`
  Strips npm boilerplate, warnings, notices, and progress chatter.
- `rtk/src/cmds/system/format_cmd.rs`
  Dispatches formatter output and reduces it to only the files that need changes or were changed.

### Python

- `rtk/src/cmds/python/ruff_cmd.rs`
  Forces structured `ruff` output where possible, groups findings, and compacts formatter output.
- `rtk/src/cmds/python/pytest_cmd.rs`
  Keeps pytest failures and summary information while dropping passing noise.
- `rtk/src/cmds/python/mypy_cmd.rs`
  Groups type errors by file.
- `rtk/src/cmds/python/pip_cmd.rs`
  Uses JSON for `list` and `outdated` where possible, then summarizes packages and upgrades.

### Go

- `rtk/src/cmds/go/go_cmd.rs`
  Filters `go test`, `build`, and `vet`; uses JSON for tests and keeps concise package results, errors, and warnings.
- `rtk/src/cmds/go/golangci_cmd.rs`
  Forces JSON and groups `golangci-lint` issues by file and rule.

### Ruby

- `rtk/src/cmds/ruby/rake_cmd.rs`
  Keeps Minitest failures and summary lines for `rake test` and Rails test runs.
- `rtk/src/cmds/ruby/rspec_cmd.rs`
  Uses JSON when possible and otherwise falls back to compact failures-only RSpec output.
- `rtk/src/cmds/ruby/rubocop_cmd.rs`
  Forces JSON and groups offenses by file, severity, and cop.

### .NET

- `rtk/src/cmds/dotnet/dotnet_cmd.rs`
  Filters `dotnet build`, `test`, `restore`, and `format`, using binlogs, TRX, and format reports to emit compact summaries.

### Cloud, infra, and network

- `rtk/src/cmds/cloud/aws_cmd.rs`
  Forces JSON and emits compact service-specific summaries for common AWS commands.
- `rtk/src/cmds/cloud/container.rs`
  Filters `docker`, `docker compose`, and `kubectl` commands by summarizing lists, trimming logs, and parsing structured output where available.
- `rtk/src/cmds/cloud/curl_cmd.rs`
  Detects JSON responses and compresses them into compact content or schema-like summaries.
- `rtk/src/cmds/cloud/wget_cmd.rs`
  Removes progress bars and reduces downloads to concise success, failure, file, or preview summaries.
- `rtk/src/cmds/cloud/psql_cmd.rs`
  Removes table borders and padding to produce compact SQL result output.

### System and generic

- `rtk/src/cmds/system/ls.rs`
  Converts `ls` output into a compact listing and summary.
- `rtk/src/cmds/system/tree.rs`
  Keeps useful tree structure while suppressing noisy directories and excess detail.
- `rtk/src/cmds/system/read.rs`
  Reads files with optional comment and boilerplate stripping plus controlled windowing.
- `rtk/src/cmds/system/json_cmd.rs`
  Shows compact JSON values or schema-only structure.
- `rtk/src/cmds/system/grep_cmd.rs`
  Groups search hits by file, trims long lines, and limits total output.
- `rtk/src/cmds/system/find_cmd.rs`
  Replaces flat `find` output with a more compact grouped representation.
- `rtk/src/cmds/system/log_cmd.rs`
  Deduplicates repeated log lines and counts repeats.
- `rtk/src/cmds/system/env_cmd.rs`
  Masks sensitive environment values and suppresses noise.
- `rtk/src/cmds/system/deps.rs`
  Summarizes dependency manifests and lockfiles.
- `rtk/src/cmds/system/summary.rs`
  Produces a heuristic summary of arbitrary command output.
- `rtk/src/cmds/system/wc_cmd.rs`
  Compacts word, line, and byte counts.
- `rtk/src/cmds/system/local_llm.rs`
  Produces a compact heuristic summary of file contents.

## Built-in TOML Filters

RTK currently embeds 58 built-in TOML filters from `rtk/src/filters/*.toml`.

### Build, lint, and formatter filters

- `ansible-playbook.toml`
  Matches `ansible-playbook`; strips play and task noise to keep the meaningful execution result.
- `basedpyright.toml`
  Matches `basedpyright`; removes blank and noisy lines while keeping type diagnostics.
- `biome.toml`
  Matches `biome`; keeps diagnostics and removes blank or noisy lines.
- `dotnet-build.toml`
  Matches `dotnet build`; strips banners and can short-circuit to a compact clean-success message.
- `gcc.toml`
  Matches `gcc` and `g++`; drops notes and boilerplate while keeping warnings and errors.
- `gradle.toml`
  Matches `gradle` and `gradlew`; removes progress and task chatter while keeping meaningful build lines.
- `hadolint.toml`
  Matches `hadolint`; keeps lint findings and removes blank or noisy lines.
- `make.toml`
  Matches `make`; strips repetitive build noise while retaining meaningful build output.
- `markdownlint.toml`
  Matches `markdownlint`; removes blank lines and caps the result size.
- `mix-compile.toml`
  Matches `mix compile`; strips compile noise and can return a short success result.
- `mix-format.toml`
  Matches `mix format`; caps output and emits a compact success fallback.
- `mvn-build.toml`
  Matches `mvn compile`, `package`, `clean`, and `install`; removes Maven noise while keeping meaningful build lines.
- `nx.toml`
  Matches `nx`; removes task graph and cache chatter while keeping final task results.
- `oxlint.toml`
  Matches `oxlint`; keeps diagnostics and strips blank or noisy lines.
- `pio-run.toml`
  Matches `pio run`; strips build chatter and emits a compact summary.
- `pre-commit.toml`
  Matches `pre-commit`; removes noise and caps output.
- `quarto-render.toml`
  Matches `quarto render`; strips render chatter and can short-circuit clean success cases.
- `shellcheck.toml`
  Matches `shellcheck`; keeps findings and caret lines while stripping blank or noisy lines.
- `shopify-theme.toml`
  Matches `shopify theme push` and `pull`; keeps a compact status-oriented tail.
- `spring-boot.toml`
  Matches common Spring Boot startup commands; uses keep-lines filtering to preserve key startup events and drop log spam.
- `swift-build.toml`
  Matches `swift build`; removes compile and link chatter and can short-circuit clean success.
- `task.toml`
  Matches `task`; removes task headers while keeping command results.
- `trunk-build.toml`
  Matches `trunk build`; removes build chatter and keeps a concise head/tail summary.
- `turbo.toml`
  Matches `turbo`; removes cache and status noise while keeping task results.
- `ty.toml`
  Matches `ty`; keeps type errors and strips blank or noisy lines.
- `xcodebuild.toml`
  Matches `xcodebuild`; removes verbose build-phase chatter while preserving warnings, errors, and summary lines.
- `yamllint.toml`
  Matches `yamllint`; removes blank lines and limits the output size.

### Package manager and dependency filters

- `brew-install.toml`
  Matches `brew install` and `upgrade`; removes download chatter and can short-circuit already-installed cases.
- `bundle-install.toml`
  Matches `bundle install` and `update`; drops repetitive `Using` lines while keeping installs and errors.
- `composer-install.toml`
  Matches `composer install`, `update`, and `require`; removes download and update chatter and can short-circuit up-to-date cases.
- `mise.toml`
  Matches `mise run`, `exec`, `install`, and `upgrade`; removes status chatter while keeping task and install results.
- `poetry-install.toml`
  Matches `poetry install`, `lock`, and `update`; removes download chatter and can short-circuit up-to-date cases.
- `uv-sync.toml`
  Matches `uv sync` and `uv pip install`; removes download and install chatter and can short-circuit up-to-date cases.

### Infra, cloud, and DevOps filters

- `fail2ban-client.toml`
  Matches `fail2ban-client`; strips noise and caps output.
- `gcloud.toml`
  Matches `gcloud`; strips noise and caps output.
- `helm.toml`
  Matches `helm`; drops verbose noise and caps output.
- `iptables.toml`
  Matches `iptables`; strips noise and truncates output.
- `rsync.toml`
  Matches `rsync`; removes progress chatter and can short-circuit clean success.
- `skopeo.toml`
  Matches `skopeo`; truncates verbose manifest and inspection output.
- `sops.toml`
  Matches `sops`; strips noise and caps output.
- `ssh.toml`
  Matches `ssh`; drops connection banners while keeping the actual command output.
- `systemctl-status.toml`
  Matches `systemctl status`; trims blank and excess lines to a concise status block.
- `terraform-plan.toml`
  Matches `terraform plan`; removes refresh and progress noise while keeping a compact plan summary.
- `tofu-fmt.toml`
  Matches `tofu fmt`; caps output and can emit an `ok` or no-change fallback.
- `tofu-init.toml`
  Matches `tofu init`; strips init chatter while keeping a concise result.
- `tofu-plan.toml`
  Matches `tofu plan`; removes plan noise while keeping a compact plan summary.
- `tofu-validate.toml`
  Matches `tofu validate`; can short-circuit clean validation output.

### System, shell, and utility filters

- `df.toml`
  Matches `df`; truncates wide rows and caps line count.
- `du.toml`
  Matches `du`; removes noise and limits output rows.
- `jq.toml`
  Matches `jq`; truncates large JSON or text results.
- `jj.toml`
  Matches `jj`; drops blank lines and truncates long output.
- `just.toml`
  Matches `just`; removes recipe headers while keeping command results.
- `ollama.toml`
  Matches `ollama run`; strips ANSI spinner and cursor control sequences while keeping final text.
- `ping.toml`
  Matches `ping`; drops per-packet lines and keeps the tail summary.
- `ps.toml`
  Matches `ps`; truncates wide lines and limits rows.
- `stat.toml`
  Matches `stat`; removes device, inode, and birth-time metadata noise.
- `yadm.toml`
  Matches `yadm`; provides a compact git-like output for yadm wrapper commands.

### Miscellaneous command filters

- `jira.toml`
  Matches `jira`; removes verbose metadata and keeps essentials.

## Notes

- Built-in TOML filters are fallback filters. They are applied when `rtk` does not route the command to a dedicated Rust subcommand first.
- `rtk/src/core/toml_filter.rs` explicitly warns when a TOML filter would be shadowed by an existing Rust-handled command.
- Some Rust modules also contain passthrough helpers for unsupported subcommands, but only the entries listed above contain filtering behavior.
