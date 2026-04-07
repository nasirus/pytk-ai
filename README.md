# PYTK-AI

A lightweight, dependency-free Python library and CLI that executes shell commands and filters their output into compact, token-efficient results for LLM consumption.

PYTK-AI reduces token usage by 25-50% across common development commands through smart filtering, deduplication, and noise removal -- helping AI coding agents work faster and cheaper.

## Features

- **Smart output filtering** -- 55+ filters for git, build tools, package managers, infrastructure commands, and more
- **Zero dependencies** -- standard library only, installs anywhere Python 3.10+ runs
- **Fail-safe design** -- if a filter fails, raw output passes through unchanged
- **Exit code preservation** -- underlying command exit codes propagate correctly
- **Compound command support** -- handles `&&`, `||`, `;`, `&`, and simple pipes
- **Embeddable** -- small enough to drop into agent toolchains, hooks, and scripts

## Installation

### From PyPI

```bash
pip install pytk-ai
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install pytk-ai
```

### From source

```bash
git clone https://github.com/nasirus/pytk-ai.git
cd pytk-ai
pip install -e .
```

## CLI Usage

```bash
pytk-ai run git status
pytk-ai run "cargo test && git push"
pytk-ai run "docker ps"
```

## Library Usage

```python
from pytk_ai.runner import run_command

result = run_command("git status")
print(result.filtered_output)
print(result.exit_code)
```

## Supported Filters

| Category | Examples | Avg Token Reduction |
|----------|----------|---------------------|
| Git | `git status`, `git log`, `git diff`, `git pull` | 40% |
| Build | `cargo build`, `tsc`, `next build` | 19% |
| Files | `find`, `wc`, `rg` | 18% |
| Go | `golangci-lint`, `go test` | 26% |
| Infrastructure | `docker ps`, `kubectl`, `aws`, `docker logs` | 46% |
| Packages | `npm list`, `pip list`, `pnpm list`, `bundle install` | 47% |
| Python | `pytest`, `mypy`, `ruff` | 24% |
| Ruby | `rubocop`, `rspec` | 30% |
| Tests | `cargo test`, `pytest` | 36% |
| Generic | ANSI stripping, progress bars, line collapse | 52% |

## How It Works

```
Command input
    |
    v
Plan/Normalize --> Execute subprocess --> Apply filter --> Structured result
                                              |
                                    (smart filtering, grouping,
                                     deduplication, truncation)
```

1. **Planning** -- determines if the command benefits from PYTK-AI filtering
2. **Execution** -- runs the command via subprocess with stdout/stderr capture
3. **Filtering** -- applies domain-specific filters to compress the output
4. **Result** -- returns a `CommandResult` with filtered output, exit code, and metadata

<!-- BENCHMARK-START -->

### Filter Benchmark Results

Token estimator: `cl100k_base`

Compared against `rtk 0.35.0`

#### By Category

| Category | Scenarios | Avg Raw Tokens | PYTK Avg Filtered | PYTK Avg Reduction | RTK Coverage | RTK Avg Filtered | RTK Avg Reduction |
|----------|-----------|----------------|-------------------|--------------------|--------------|------------------|-------------------|
| build | 8 | 155 | 138 | 10.5% | 8/8 | 81 | 47.8% |
| files | 6 | 272 | 187 | 31.1% | 6/6 | 230 | 15.3% |
| generic | 2 | 8 | 4 | 56.2% | 2/2 | 6 | 25.0% |
| git | 8 | 44 | 25 | 44.2% | 7/8 | 20 | 56.1% |
| go | 2 | 438 | 244 | 44.1% | 1/2 | 6 | 84.2% |
| infra | 11 | 68 | 35 | 49.4% | 10/11 | 38 | 44.2% |
| packages | 8 | 57 | 26 | 53.7% | 8/8 | 46 | 19.7% |
| python | 3 | 147 | 108 | 26.9% | 3/3 | 128 | 13.1% |
| ruby | 2 | 158 | 139 | 11.7% | 2/2 | 124 | 21.3% |
| system | 4 | 528 | 494 | 6.3% | 4/4 | 56 | 89.4% |
| tests | 2 | 40 | 35 | 12.5% | 2/2 | 46 | -16.2% |
| **Total** | **56** | **148** | **110** | **25.5%** | **53/56** | **73** | **47.0%** |

#### Scenario Comparison (Top 25)

| Scenario | Command | Raw | PYTK | PYTK Red. | RTK | RTK Red. | Winner |
|----------|---------|-----|------|-----------|-----|----------|--------|
| packages/pnpm_list_json | `pnpm list --json` | 35 | 15 | 57.1% | 50 | -42.9% | PYTK +100.0pp |
| system/tail_repeated | `tail server.log` | 1,922 | 1,922 | 0.0% | 170 | 91.2% | RTK +91.2pp |
| git/add_warning | `git add vendor/lib` | 32 | 32 | 0.0% | 5 | 84.4% | RTK +84.4pp |
| build/biome_lint | `biome lint src` | 323 | 318 | 1.5% | 63 | 80.5% | RTK +79.0pp |
| go/go_test_fail | `go test ./...` | 38 | 36 | 5.3% | 6 | 84.2% | RTK +78.9pp |
| infra/kubectl_pods_json | `kubectl get pods -A -o json` | 96 | 21 | 78.1% | 96 | 0.0% | PYTK +78.1pp |
| build/eslint_stylish | `eslint src` | 354 | 321 | 9.3% | 54 | 84.7% | RTK +75.4pp |
| infra/docker_logs | `docker logs web` | 185 | 148 | 20.0% | 31 | 83.2% | RTK +63.2pp |
| infra/kubectl_services | `kubectl get services` | 56 | 22 | 60.7% | 56 | 0.0% | PYTK +60.7pp |
| packages/npm_list | `npm list` | 215 | 87 | 59.5% | 215 | 0.0% | PYTK +59.5pp |
| infra/kubectl_pods_table | `kubectl get pods -A` | 67 | 31 | 53.7% | 67 | 0.0% | PYTK +53.7pp |
| infra/docker_images | `docker images` | 45 | 18 | 60.0% | 41 | 8.9% | PYTK +51.1pp |
| build/cargo_build_error | `cargo build` | 82 | 57 | 30.5% | 95 | -15.9% | PYTK +46.4pp |
| build/next_build_ok | `next build` | 76 | 57 | 25.0% | 23 | 69.7% | RTK +44.7pp |
| python/ruff_check | `ruff check .` | 40 | 39 | 2.5% | 56 | -40.0% | PYTK +42.5pp |
| git/commit_success | `git commit -m "Add compact filter"` | 17 | 8 | 52.9% | 1 | 94.1% | RTK +41.2pp |
| ruby/rspec_failures | `rspec` | 79 | 54 | 31.6% | 86 | -8.9% | PYTK +40.5pp |
| generic/ansi_output | `echo test` | 5 | 3 | 40.0% | 5 | 0.0% | PYTK +40.0pp |
| git/status_dirty | `git status` | 103 | 54 | 47.6% | 17 | 83.5% | RTK +35.9pp |
| git/log_full | `git log -2` | 65 | 18 | 72.3% | 40 | 38.5% | PYTK +33.8pp |
| infra/docker_ps | `docker ps` | 76 | 30 | 60.5% | 6 | 92.1% | RTK +31.6pp |
| tests/cargo_test_fail | `cargo test` | 44 | 45 | -2.3% | 58 | -31.8% | PYTK +29.5pp |
| tests/npm_test_fail | `npm test` | 36 | 25 | 30.6% | 35 | 2.8% | PYTK +27.8pp |
| build/cargo_fmt_check | `cargo fmt --check` | 58 | 42 | 27.6% | 58 | 0.0% | PYTK +27.6pp |
| system/cat_missing | `cat missing.txt` | 11 | 11 | 0.0% | 14 | -27.3% | PYTK +27.3pp |

<!-- BENCHMARK-END -->

## License

MIT License

## Acknowledgements

PYTK-AI is a Python port of **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)**, a high-performance Rust CLI proxy that reduces LLM token consumption by 60-90%. The filtering strategies, command coverage, and architectural patterns in this project are derived from RTK's design.

## Citation

If you use PYTK-AI or RTK in your research or tooling, please cite the original project:

```bibtex
@software{rtk2024,
  title     = {RTK: Rust Token Killer},
  author    = {RTK AI},
  url       = {https://github.com/rtk-ai/rtk},
  year      = {2024},
  note      = {High-performance CLI proxy that reduces LLM token consumption by 60-90\%}
}
```
