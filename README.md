# PTK (Python)

This repository is a Python port of the PTK command rewrite engine.

## What it does

- rewrites agent shell commands like `git status` to `ptk git status`
- preserves compound commands such as `&&`, `||`, `;`, and `&`
- exposes a small CLI for use in agent hooks

## Install locally

```bash
pip install -e .
```

## Usage

```bash
ptk rewrite "git status"
ptk rewrite "cargo test && git push"
```

The package is intentionally small and dependency-free so it can be embedded in
agent toolchains and hook scripts.
