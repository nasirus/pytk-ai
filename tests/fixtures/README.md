# Test Fixtures

Each fixture is a set of 2-3 files sharing a base name:

- `name.stdout` — captured raw stdout
- `name.stderr` — captured raw stderr (optional)
- `name.meta` — JSON metadata: `{"command": "...", "exit_code": 0, "filter_name": "..."}`

## Directory layout

Fixtures are organized by filter domain:

```
fixtures/
  git/           # git commands
  infra/         # docker, kubectl, terraform, aws
  build/         # cargo build/clippy/fmt, eslint, biome, tsc, next
  python/        # ruff, mypy, pytest
  packages/      # pip, uv, npm, pnpm, bundle, prisma
  files/         # rg, find, tree, wc, diff
  system/        # ls, cat, tail
  go/            # go test, golangci-lint
  ruby/          # rubocop, rspec
  tests/         # generic test wrappers, cargo test
  generic/       # generic filter edge cases
```

## Capturing new fixtures

Use the helper script:

```bash
./scripts/capture_fixtures.sh <category> <command> <name>
# Example:
./scripts/capture_fixtures.sh git "git status" status_dirty
```
