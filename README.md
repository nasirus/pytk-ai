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
pytk-ai run --timeout 10 git status
pytk-ai run "cargo test && git push"
pytk-ai run "docker ps"
```

## Library Usage

```python
from pytk_ai.runner import run_command

result = run_command("git status")
slow_result = run_command("pytest -q", timeout=120)
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
| build | 8 | 386 | 215 | 44.3% | 8/8 | 113 | 70.8% |
| files | 6 | 114 | 70 | 38.4% | 6/6 | 91 | 20.1% |
| generic | 2 | 82 | 26 | 68.9% | 2/2 | 25 | 69.5% |
| git | 8 | 151 | 52 | 65.6% | 7/8 | 31 | 73.7% |
| go | 2 | 320 | 192 | 39.9% | 1/2 | 6 | 94.8% |
| infra | 11 | 3,605 | 74 | 98.0% | 10/11 | 3,811 | 3.6% |
| packages | 8 | 359 | 78 | 78.3% | 8/8 | 72 | 79.9% |
| python | 3 | 219 | 98 | 55.4% | 3/3 | 163 | 25.6% |
| ruby | 2 | 435 | 302 | 30.6% | 2/2 | 172 | 60.3% |
| system | 4 | 106 | 56 | 46.4% | 4/4 | 65 | 38.2% |
| tests | 2 | 430 | 126 | 70.7% | 2/2 | 270 | 37.4% |
| **Total** | **56** | **913** | **104** | **88.7%** | **53/56** | **793** | **16.1%** |

#### Scenario Comparison (Top 25)

| Scenario | Command | Raw | PYTK | PYTK Red. | RTK | RTK Red. | Winner |
|----------|---------|-----|------|-----------|-----|----------|--------|
| infra/kubectl_pods_json | `kubectl get pods -A -o json` | 37,112 | 32 | 99.9% | 37,112 | 0.0% | PYTK +99.9pp |
| files/wc_multi | `wc src/app.py tests/test_app.py` | 20 | 39 | -95.0% | 20 | 0.0% | RTK +95.0pp |
| infra/kubectl_pods_table | `kubectl get pods -A` | 369 | 33 | 91.1% | 369 | 0.0% | PYTK +91.1pp |
| infra/aws_ec2 | `aws ec2 describe-instances --output json` | 7 | 10 | -42.9% | 4 | 42.9% | RTK +85.8pp |
| python/ruff_check | `ruff check .` | 261 | 60 | 77.0% | 277 | -6.1% | PYTK +83.1pp |
| build/biome_lint | `biome lint src` | 830 | 731 | 11.9% | 63 | 92.4% | RTK +80.5pp |
| build/cargo_fmt_check | `cargo fmt --check` | 262 | 56 | 78.6% | 262 | 0.0% | PYTK +78.6pp |
| tests/npm_test_fail | `npm test` | 197 | 41 | 79.2% | 189 | 4.1% | PYTK +75.1pp |
| go/go_test_fail | `go test ./...` | 116 | 88 | 24.1% | 6 | 94.8% | RTK +70.7pp |
| build/next_build_fail | `next build` | 298 | 222 | 25.5% | 20 | 93.3% | RTK +67.8pp |
| infra/docker_logs | `docker logs web` | 27 | 49 | -81.5% | 31 | -14.8% | RTK +66.7pp |
| infra/kubectl_services | `kubectl get services` | 78 | 34 | 56.4% | 78 | 0.0% | PYTK +56.4pp |
| packages/uv_sync_ok | `uv sync` | 135 | 67 | 50.4% | 135 | 0.0% | PYTK +50.4pp |
| system/tail_repeated | `tail server.log` | 68 | 34 | 50.0% | 68 | 0.0% | PYTK +50.0pp |
| build/eslint_stylish | `eslint src` | 504 | 283 | 43.8% | 54 | 89.3% | RTK +45.5pp |
| ruby/rubocop_offenses | `rubocop` | 745 | 529 | 29.0% | 223 | 70.1% | RTK +41.1pp |
| git/branch_vv | `git branch -vv` | 88 | 56 | 36.4% | 91 | -3.4% | PYTK +39.8pp |
| files/tree_output | `tree` | 94 | 50 | 46.8% | 87 | 7.4% | PYTK +39.4pp |
| infra/docker_ps | `docker ps` | 306 | 122 | 60.1% | 6 | 98.0% | RTK +37.9pp |
| ruby/rspec_failures | `rspec` | 125 | 75 | 40.0% | 122 | 2.4% | PYTK +37.6pp |
| git/status_dirty | `git status` | 265 | 121 | 54.3% | 23 | 91.3% | RTK +37.0pp |
| build/cargo_build_error | `cargo build` | 192 | 70 | 63.5% | 131 | 31.8% | PYTK +31.7pp |
| files/rg_matches | `rg main` | 384 | 228 | 40.6% | 345 | 10.2% | PYTK +30.4pp |
| system/cat_missing | `cat missing.txt` | 11 | 11 | 0.0% | 14 | -27.3% | PYTK +27.3pp |
| packages/pip_list | `pip list` | 192 | 71 | 63.0% | 20 | 89.6% | RTK +26.6pp |

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
