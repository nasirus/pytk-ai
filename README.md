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

#### By Category

| Category | Scenarios | Avg Raw Tokens | Avg Filtered | Avg Reduction |
|----------|-----------|---------------|-------------|---------------|
| build | 8 | 155 | 138 | 18.6% |
| files | 6 | 272 | 192 | 18.4% |
| generic | 2 | 8 | 4 | 51.8% |
| git | 8 | 44 | 25 | 40.5% |
| go | 2 | 438 | 244 | 25.6% |
| infra | 11 | 68 | 35 | 46.4% |
| packages | 8 | 57 | 26 | 46.9% |
| python | 3 | 147 | 108 | 24.2% |
| ruby | 2 | 158 | 130 | 30.4% |
| system | 4 | 528 | 494 | 19.4% |
| tests | 2 | 40 | 26 | 35.8% |
| **Total** | **56** | | | **25.6%** |

#### Top Filters by Token Reduction

| Filter | Command | Raw | Filtered | Saved | Reduction |
|--------|---------|-----|----------|-------|-----------|
| git.pull | `git pull` | 28 | 4 | 24 | 85.7% |
| kubectl.pods | `kubectl get pods -A -o json` | 96 | 21 | 75 | 78.1% |
| system.ls | `ls -la` | 173 | 39 | 134 | 77.5% |
| git.log | `git log -2` | 65 | 18 | 47 | 72.3% |
| aws.read | `aws ec2 describe-instances --output json` | 74 | 21 | 53 | 71.6% |
| python.pytest | `pytest -q` | 165 | 55 | 110 | 66.7% |
| git.diff | `git diff` | 41 | 14 | 27 | 65.9% |
| bundle.install | `bundle install` | 55 | 19 | 36 | 65.5% |
| git.status | `git status` | 11 | 4 | 7 | 63.6% |
| kubectl.services | `kubectl get services` | 56 | 22 | 34 | 60.7% |
| docker.ps | `docker ps` | 76 | 30 | 46 | 60.5% |
| docker.images | `docker images` | 45 | 18 | 27 | 60.0% |
| uv.sync | `uv sync` | 15 | 6 | 9 | 60.0% |
| docker.compose.ps | `docker compose ps` | 67 | 27 | 40 | 59.7% |
| npm.list | `npm list` | 215 | 87 | 128 | 59.5% |

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
