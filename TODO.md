# TODO

## Active work

- [ ] Expand rewrite coverage beyond the current core rule set.
- [ ] Port the remaining hook integrations if needed by the target agent harness.
- [ ] Add packaging/release automation for PyPI.
- [ ] Decide whether PTK should keep compatibility aliases for legacy RTK environment variables and hook outputs.

## Next priorities

1. Confirm the exact public CLI surface for PTK.
2. Port the remaining command families from the Rust reference.
3. Add regression tests for the edge cases we already know about.

## History

- 2026-04-05: Created the initial Python PTK scaffold, renamed the package from `rtk` to `ptk`, and verified the core rewrite flow.
- 2026-04-05: Added the first hook JSON responses for Claude and Cursor.
- 2026-04-05: Added token-frugal mode guidance to `INSTRUCTIONS.md`, including the prompt block and terse-output safety notes.
