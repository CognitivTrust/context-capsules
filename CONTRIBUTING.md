# Contributing to Context Capsules

First off — thank you. Context Capsules is a small, focused, local-first tool, and it stays good by staying small. Thoughtful contributions of any size are welcome: a typo fix, a sharper error message, a test for an edge case, a new evidence verifier, or a well-argued change to the event standard.

This document explains how to get set up, how we work, and what we expect. If anything here is unclear, open a [Discussion](https://github.com/CognitivTrust/context-capsules/discussions) and we'll fix the docs.

## Table of contents

- [Maintainer](#maintainer)
- [Project principles (read this first)](#project-principles-read-this-first)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Development workflow](#development-workflow)
- [Coding standards](#coding-standards)
- [Tests](#tests)
- [Commit conventions](#commit-conventions)
- [Pull request process](#pull-request-process)
- [Reporting issues](#reporting-issues)
- [Changing the event schema](#changing-the-event-schema)
- [Community expectations](#community-expectations)

## Maintainer


| Name      | GitHub                                         | Role                                 |
| --------- | ---------------------------------------------- | ------------------------------------ |
| Yash Shah | [@yashshah-ct](https://github.com/yashshah-ct) | Project creator and sole maintainer |


Yash Shah currently triages issues, reviews pull requests, stewards the event standard, and cuts releases. See [GOVERNANCE.md](GOVERNANCE.md) for how project decisions are made.

## Project principles (read this first)

Before you write code, internalize the invariants. A PR that violates one of these will be asked to change, no matter how clean it is.

1. **Local-first: zero network.** No telemetry, no analytics, no phone-home, no accounts, no exceptions — nothing in this tool ever makes a network call, not even at the CLI edge.
2. **In-repo capsule storage.** V1 stores capsule data at `.capsule/log.jsonl` + `.capsule/capsule.md` + `.capsule/.lock`. Avoid adding selection state or extra storage surfaces without strong justification.
3. **JSONL is the source of truth.** `capsule.md` is a regenerable render and is never read back as truth.
4. **Events are immutable and append-only.** Never rewrite a prior line. An "edit" is a new event; a `revert` is a compensating event.
5. **Existence verification only.** Evidence checks confirm a cited file/commit/test/url *exists*, deterministically and locally. Never semantic or behavioral verification.
6. `verified: false` **is data, not an error.** The engine never raises because evidence is missing.
7. **Minimal dependency budget is a feature.** A change that adds a dependency, a network call, or expands the storage surface needs an explicit justification against these invariants first.

When in doubt, prefer deleting code over adding it.

## Ways to contribute

- **Report bugs** with a minimal reproduction (see [Reporting issues](#reporting-issues)).
- **Improve docs**: README, SETUP, the `docs/` guides, error messages, examples.
- **Add tests** for edge cases, especially around concurrency, encoding, and crash recovery.
- **Fix bugs** that already have an issue and are labeled `help wanted` / `good first issue`.
- **Add an evidence verifier** for a new ref kind (see the `evidence-verification` design notes in the engine).
- **Propose a change to the standard** via a [spec change issue](https://github.com/CognitivTrust/context-capsules/issues/new?template=spec_change.yml), these get extra scrutiny.

For anything larger than a bug fix or a docs change, **open an issue or discussion first** so we can agree on the approach before you invest time.

## Development setup

You need **Python 3.11+** and Git.

### Windows (PowerShell)

```powershell
git clone https://github.com/CognitivTrust/context-capsules.git
cd context-capsules
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```



### macOS / Linux

```bash
git clone https://github.com/CognitivTrust/context-capsules.git
cd context-capsules
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Verify the toolchain:

```bash
capsule --version
ruff check .
ruff format --check .
mypy
pytest
```

All four checks must pass before you open a PR. They are exactly what CI runs.

## Development workflow

1. **Find or open an issue.** Comment that you're picking it up so we don't duplicate work.
2. **Branch** from `main` with a descriptive name: `fix/torn-line-recovery`, `feat/url-verifier`, `docs/quickstart`.
3. **Make the change** in small, reviewable commits.
4. **Add or update tests** that prove the change and would fail without it.
5. **Run the full local check** (`ruff`, `ruff format`, `mypy`, `pytest`).
6. **Update docs** (`README.md`, `SETUP.md`, `docs/`) and add a `CHANGELOG.md` entry under `[Unreleased]`.
7. **Open a pull request** against `main` and fill out the template.

This project dogfoods itself. If you make a consequential decision while working, consider recording it:

```bash
capsule record decision --by "your-name" \
  --decision "what you chose" --rationale "why" --evidence file:path/to/changed.py
```



## Coding standards

The full standard lives in `.cursor/rules/python-code-standards.mdc`; the essentials:

- **Target Python 3.11+.** Lint with `ruff`, format with `ruff format`, type-check with `mypy --strict`.
- **Full type hints on every function signature.** Avoid `Any`; validate external input once at the boundary, then trust the typed value.
- **Small, single-purpose functions** (aim under ~40 lines).
- **Use** `@dataclass(frozen=True)` for events and value objects — immutability mirrors the append-only model.
- **Use the project's typed errors** (`SchemaError`, `LockTimeout`, `NoCapsule`, `EvidenceUnreadable`, `CorruptLogLine`, …). Never `raise Exception`, never a bare `except:`, never a silent default.
- **Fail loud; never mask.** A corrupt last log line is *quarantined* with a surfaced warning, not hidden.
- **All durable writes are atomic** (tmp file + `os.replace`), then re-render. A `kill -9` must leave either the old file or the new one, never a partial.
- **Stay cross-platform.** Use `pathlib.Path`, explicit `encoding="utf-8"` (and `newline=""` where line integrity matters), and `portalocker` for locking, never POSIX-only `fcntl`.



## Tests

- Tests live in `tests/` and run with `pytest`.
- New behavior needs a test; bug fixes need a regression test that fails before the fix.
- Prefer deterministic, golden-file tests (see `tests/fixtures/`) for fold and render.
- Keep tests cross-platform — no hardcoded path separators, no POSIX-only assumptions.
- The engine and store have the strictest coverage expectations because they own data integrity.

Run a focused subset while iterating:

```bash
pytest tests/test_fold.py -q
pytest -k "lock or store" -q
```



## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/). The type prefix drives the changelog and the release version bump.

```
<type>(optional scope): <short, imperative summary>
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`.

Examples:

```
feat(verify): add url existence verifier behind --check-urls
fix(store): quarantine torn final line instead of raising
docs(readme): clarify local-first network invariant
```

Mark breaking changes with a `!` after the type/scope (`feat!:`) and a `BREAKING CHANGE:` footer. Keep the subject line under ~72 characters and write in the imperative mood.

## Pull request process

1. Make sure CI is green (lint, format, types, tests on all supported OSes and Python versions).
2. Fill out the PR template completely — what, why, how tested, and which invariants it touches.
3. Keep PRs small and focused. One logical change per PR.
4. Link the issue the PR closes (`Closes #123`).
5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Yash Shah, as the current sole maintainer, reviews; address feedback by pushing new commits.
7. The maintainer merges with **squash merge** so the commit history on `main` stays a clean, conventional log.

By contributing, you agree your contributions are licensed under the project's [Apache License 2.0](LICENSE).

## Reporting issues

- **Bugs:** use the [bug report template](https://github.com/CognitivTrust/context-capsules/issues/new?template=bug_report.yml). Include OS, Python version, `capsule --version`, exact commands, and `capsule doctor` output.
- **Features:** use the [feature request template](https://github.com/CognitivTrust/context-capsules/issues/new?template=feature_request.yml). Explain the problem before the solution, and check it against the project principles.
- **Security:** do **not** open a public issue. See [SECURITY.md](SECURITY.md).
- **Questions / ideas:** use [GitHub Discussions](https://github.com/CognitivTrust/context-capsules/discussions).



## Changing the event schema

The on-disk format is a contract that other tools depend on. Changes are governed:

- **Additive, backward-compatible changes** (a new optional field, a new event type) require a **MINOR** schema bump and a conformance test.
- **Breaking changes** (rename, remove, retype, or change required-ness) require a **MAJOR** bump, a written rationale, and a conformance test update.
- Use the [spec change issue template](https://github.com/CognitivTrust/context-capsules/issues/new?template=spec_change.yml) and expect a longer review.

Forward compatibility is non-negotiable: unknown fields are preserved and round-tripped, never dropped or rejected.

## Community expectations

- Be kind, be specific, assume good faith. All interaction is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
- Reviews critique code, not people. Disagreement is fine; disrespect is not.
- This is a single-maintainer project. A nudge after a week of silence is welcome; pressure is not.

Thanks again for helping make project memory a first-class primitive.