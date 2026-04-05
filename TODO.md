# TODO

## Active work

- Define the PTK high-level architecture around an internal planning step plus public execute + strip library/CLI flow.


## Next priorities

1. Decompose the architecture into a set of Python modules and classes that can be implemented incrementally.
2. Implement the core command rewrite flow in Python, using the existing Rust code as a reference for logic and behavior.

## History

- 2026-04-05: Created the initial Python PTK scaffold, renamed the package from `rtk` to `ptk`, and verified the core rewrite flow.
- 2026-04-05: Added the first hook JSON responses for Claude and Cursor.
- 2026-04-05: Added token-frugal mode guidance to `INSTRUCTIONS.md`, then tightened it into a brief XML-tagged prompt block.
- 2026-04-05: Simplified `ARCHITECTURE.md` so `ptk run` is the main public interface and command rewrite remains an internal planning step rather than a required public CLI feature.
- 2026-04-05: Added `ARCHITECTURE.md` to define the PTK target architecture as a Python library/CLI for command rewrite, execution, and stripped output.