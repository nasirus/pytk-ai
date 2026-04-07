# Real Fixture Capture Checklist

Goal: replace synthetic fixture payloads with output captured from real bash commands, then store that output as the fixture source of truth.

Scope: prioritized from the fixture regression suites in `tests/test_fixtures_*.py`. Secondary fixture directories that are not currently covered by those suites are listed at the end.

Realism rule for every capture:
- [ ] Prefer representative real-world output over tiny toy snippets.
- [ ] When a command naturally produces richer output, capture a scenario with multiple sections, multiple entries, realistic file or resource names, and mixed states or severities.
- [ ] Avoid minimal one-item demos unless the command is inherently terse.
- [ ] Preserve the real stdout/stderr split; if a tool writes its human-facing log to stderr, keep it there instead of inventing stdout content.

Capture flow:
- [ ] Create or reuse a minimal real project/environment for the target command.
- [ ] Run the exact command in `bash`.
- [ ] Capture stdout/stderr into the existing fixture shape with `./scripts/capture_fixtures.sh <category> "<command>" <name>`.
- [ ] Keep paired success/failure fixtures where noted.
- [ ] Update `.meta` only when the real command text or exit code needs to change.

## P0: Local, high-leverage, easy to reproduce

- [x] `git status` -> `git/status_dirty`
- [x] `git diff` -> `git/diff_multifile`
- [x] `git log -2` -> `git/log_full`
- [x] `git branch -vv` -> `git/branch_vv`
- [x] `git add vendor/lib` -> `git/add_warning`
- [x] `git show missing` -> `git/show_failure`
- [x] `git commit -m "Add compact filter"` -> `git/commit_success`
- [x] `git pull` -> `git/pull_fastforward`
- [x] `rg main` -> `files/rg_matches`
- [x] `rg [ src` -> `files/rg_error`
- [x] `find . -name '*.py'` -> `files/find_results`
- [x] `tree` -> `files/tree_output`
- [x] `wc src/app.py tests/test_app.py` -> `files/wc_multi`
- [x] `diff -u a.txt b.txt` -> `files/diff_unified`
- [x] `ls -la` -> `system/ls_la`
- [x] `cat missing.txt` -> `system/cat_missing`
- [x] `cat tailwind.config.js` -> `system/cat_tailwind`
- [x] `tail server.log` -> `system/tail_repeated`
- [x] `ruff check .` -> `python/ruff_check`
- [x] `mypy src` -> `python/mypy_errors`
- [x] `pytest -q` -> `python/pytest_failures`

## P1: Real project/toolchain capture, still local

- [x] `pip list` -> `packages/pip_list`
- [x] `uv pip list --outdated --format json` -> `packages/pip_outdated_json`
- [x] `uv sync` -> `packages/uv_sync_ok`
- [x] `npm list` -> `packages/npm_list`, `packages/npm_list_error`
- [x] `pnpm list --json` -> `packages/pnpm_list_json`
- [x] `bundle install` -> `packages/bundle_install`
- [x] `npx prisma generate` -> `packages/prisma_generate`
- [x] `cargo build` -> `build/cargo_build_error`
- [x] `cargo clippy --all-targets` -> `build/cargo_clippy`
- [x] `cargo fmt --check` -> `build/cargo_fmt_check`
- [x] `eslint src` -> `build/eslint_stylish`
- [x] `biome lint src` -> `build/biome_lint`
- [x] `tsc --noEmit` -> `build/tsc_errors`
- [x] `next build` -> `build/next_build_ok`, `build/next_build_fail`
- [x] `go test ./...` -> `go/go_test_fail`
- [x] `golangci-lint run` -> `go/golangci_lint`
- [x] `rubocop` -> `ruby/rubocop_offenses`
- [x] `rspec` -> `ruby/rspec_failures`

## P2: Service-backed or heavier environment setup

- [x] `docker ps` -> `infra/docker_ps`
- [x] `docker images` -> `infra/docker_images`
- [x] `docker logs web` -> `infra/docker_logs`
- [x] `docker compose ps` -> `infra/docker_compose_ps`
- [x] `kubectl get pods -A` -> `infra/kubectl_pods_table`
- [x] `kubectl get pods -A -o json` -> `infra/kubectl_pods_json`
- [x] `kubectl get services` -> `infra/kubectl_services`
- [x] `terraform plan` -> `infra/terraform_plan`
- [x] `terraform validate` -> `infra/terraform_validate_ok`, `infra/terraform_validate_fail`
- [x] `aws ec2 describe-instances --output json` -> `infra/aws_ec2`

## Secondary: Previously Uncovered Fixture Dirs

- [x] `printf '\033[31mERROR\033[0m build failed\n\033[33mWARN\033[0m cache miss\n\033[32mPASS\033[0m 3 tests\nplain detail\nextra context line\n'` -> `generic/ansi_output`
- [x] `git status` -> `generic/git_status_hints`
- [x] `cargo test --no-fail-fast` -> `tests/cargo_test_fail`
- [x] `npm test` -> `tests/npm_test_fail`
