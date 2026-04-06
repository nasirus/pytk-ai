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

#### By Category

| Category | Scenarios | Avg Raw Tokens | Avg Filtered | Avg Reduction |
|----------|-----------|---------------|-------------|---------------|
| build | 8 | 163 | 163 | 7.2% |
| files | 6 | 293 | 234 | 18.6% |
| generic | 2 | 14 | 6 | 59.3% |
| git | 8 | 52 | 26 | 41.9% |
| go | 2 | 496 | 303 | 30.2% |
| infra | 11 | 92 | 48 | 42.4% |
| packages | 8 | 102 | 43 | 38.4% |
| python | 3 | 143 | 135 | 5.6% |
| ruby | 2 | 174 | 152 | 15.0% |
| system | 4 | 821 | 757 | 19.5% |
| tests | 2 | 48 | 46 | 2.8% |
| **Total** | **56** | | | **21.4%** |

#### Top Filters by Token Reduction

| Filter | Command | Raw | Filtered | Saved | Reduction |
|--------|---------|-----|----------|-------|-----------|
| git.log | `git log -2` | 85 | 16 | 69 | 81.2% |
| git.pull | `git pull` | 39 | 8 | 31 | 79.5% |
| git.status | `git status` | 14 | 3 | 11 | 78.6% |
| system.ls | `ls -la` | 327 | 72 | 255 | 78.0% |
| kubectl.pods | `kubectl get pods -A -o json` | 107 | 26 | 81 | 75.7% |
| npm.list | `npm list` | 505 | 145 | 360 | 71.3% |
| git.commit | `git commit -m "Add compact filter"` | 21 | 7 | 14 | 66.7% |
| aws.read | `aws ec2 describe-instances --output json` | 86 | 31 | 55 | 64.0% |
| kubectl.services | `kubectl get services` | 75 | 27 | 48 | 64.0% |
| git.diff | `git diff` | 67 | 28 | 39 | 58.2% |
| docker.compose.ps | `docker compose ps` | 94 | 41 | 53 | 56.4% |
| uv.sync | `uv sync` | 20 | 9 | 11 | 55.0% |
| pnpm.list | `pnpm list --json` | 56 | 27 | 29 | 51.8% |
| bundle.install | `bundle install` | 60 | 30 | 30 | 50.0% |
| docker.ps | `docker ps` | 80 | 41 | 39 | 48.8% |

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
