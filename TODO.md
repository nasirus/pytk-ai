# TODO

## Active work



## Next priorities



## History

- 2026-04-08: Added a shared default command timeout for Python and CLI entry points, exposed numeric `--timeout` on command-executing CLI subcommands, and documented library/CLI timeout overrides.
- 2026-04-08: Restored benchmark CLI compatibility by adding `python -m benchmarks.runner --fixture-only` support, added regression coverage for the parser/engine selection, and fixed the GitHub workflow summary step to read the v2 benchmark document shape.
- 2026-04-08: Fixed `git` filter regressions by preserving successful `git add` warnings, restoring detached/no-branch `git status` accuracy, and reintroducing token-efficiency guards with regression and fixture coverage.
