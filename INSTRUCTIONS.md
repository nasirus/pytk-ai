# PYTK-AI Project Instructions

You are working in the PYTK-AI codebase: a Python port of the RTK command-rewrite engine.

## Mission

- Keep the public name **PYTK-AI**.
- Treat the legacy Rust tree in `rtk/` as read-only reference material.
- Focus on command rewriting, hook integration, packaging, and testability.

## Operating rules

- Prefer small, incremental changes.
- Preserve backward compatibility when it does not conflict with the PYTK-AI rename.
- Keep public-facing strings and CLI behavior aligned with `pytk-ai`.
- Use the existing tests as the first safety net; add tests when behavior changes.
- Avoid duplicating logic across files if a single source of truth can be used.

## Project boundaries

- This repository is a Python package, not a Rust rebuild.
- The goal is to expose a small, dependency-light library and CLI that can be shipped on PyPI.
- Do not introduce unnecessary framework overhead.

## When making changes

- Record meaningful progress in `TODO.md`.
- If you discover a non-obvious constraint or failure mode, capture it so future work does not repeat the mistake.

<token_frugal_mode>
TERSE MODE — ACTIVE

Use minimum words.
No filler, narration, or sign-offs.
Default flow: Action → Result → Stop.
Explain only when asked or when risk, ambiguity, or failure requires it.
Use short status fragments.
Protect code, commands, paths, JSON, errors, and identifiers exactly.
Internal reasoning stays thorough; only visible output is compressed.

For destructive, security-sensitive, or irreversible work, use concise full sentences.
</token_frugal_mode>
