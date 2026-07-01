## Summary

<!-- What does this PR do? One or two sentences. -->

Closes #<!-- issue number -->

## Type of change

- [ ] Bug fix
- [ ] New feature / command
- [ ] Schema change (also requires a spec change issue)
- [ ] Documentation
- [ ] Refactor / cleanup
- [ ] CI / build

## What changed and why

<!-- Explain the approach you took and why. If there were meaningful alternatives, note why you chose this one. -->

## Invariant check

<!-- The project has hard invariants. Confirm this PR respects them. -->

- [ ] No network calls added to the core engine path.
- [ ] No new storage-selection or storage-management layer added without explicit justification.
- [ ] Events remain immutable and append-only (no log rewriting).
- [ ] `verified: false` is returned as data, not raised as an error.
- [ ] Any new dependency is justified against the minimalism policy in `CONTRIBUTING.md`.

## Testing

<!-- How did you test this change? -->

- [ ] Added or updated tests that cover the change.
- [ ] `pytest` passes locally.
- [ ] `ruff check .` passes.
- [ ] `ruff format --check .` passes.
- [ ] `mypy` passes.
- [ ] Tested on Windows / macOS / Linux (note which).

## Documentation

- [ ] Updated `CHANGELOG.md` under `[Unreleased]`.
- [ ] Updated `README.md`, `SETUP.md`, or `docs/` where relevant.
- [ ] Updated tests and any relevant public docs if the schema changed.

## Notes for reviewers

<!-- Anything the reviewer should know: tricky parts, open questions, deliberate trade-offs. -->
