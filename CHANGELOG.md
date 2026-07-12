# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- Cold-start intent drafting from `capsule init`, including the git-history heuristic, the BYO-key LLM path, and their flags (`--draft`, `--no-git`, `--model`). `capsule init` now only creates empty `.capsule/` storage. Agents are expected to seed the first `intent` themselves via `capsule record` after inspecting the repo — see the updated `SKILL.md`.

### Fixed

- Global flags (`--repo`, `--format`, `--verbose`) are now accepted after `record <kind>` and `task <verb>` subcommands, not just before the top-level command, matching the documented "global on every command" behavior.

Initial alpha cut of **Context Capsules**: a local-first, append-only decision log stored in-repo, driven by `capsule` CLI. This establishes the first usable V1 surface for local installs from source while the project is still preparing for a broader public release.

### Added

- Pre-launch project files for contributors and early adopters: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `GOVERNANCE.md`, `.editorconfig`, and FAQ / troubleshooting docs.
- GitHub community scaffolding for issues, discussions, pull requests, funding, code ownership, CI, and release automation.
- Public-facing project docs and packaging updates for the first OSS commit, including `README.md`, `SETUP.md`, packaging metadata, and repository templates aligned to the current CLI-first, local-first V1.
- **`context-capsule` package** available for local editable install with `pip install -e .`, exposing the `capsule` console script and `python -m capsule` entry point. Requires Python 3.11+. One runtime dependency: `portalocker` for cross-platform file locking.
- **Capsule Event Standard v0.1.0**: typed, append-only JSONL events for `intent`, `decision`, `question`, `resolution`, `progress`, `task_start`, and `task_end`, with optional evidence refs (`file`, `commit`, `test`, `url`).
- **In-repo storage layout**: `.capsule/log.jsonl` (source of truth), `.capsule/capsule.md` (regenerable human render), and `.capsule/.lock` (transient advisory lock).
- **Core engine**: schema validation, deterministic fold (events to projection), atomic markdown render, torn-line quarantine on crash-interrupted appends, forward-compatible unknown-field round-trip, and linkage validation for `resolution` and `task_end` events.
- **Existence-only evidence verification**: stamps `verified: true` or `verified: false` on decisions and progress that cite evidence. Files, commits, and test targets are checked locally; URLs are syntax-validated only.
- **CLI commands**: `init`, `load`, `show`, `doctor`, `record`, `task`, `log`, `context`, and `apply`.
- **Typed CLI exit codes**: `0` OK, `1` ERROR, `2` USAGE, `3` NO_CAPSULE, `4` SCHEMA, `5` LOCK_TIMEOUT, `6` CORRUPT_LOG, `7` EVIDENCE_UNREADABLE.
- **Windows-safe CLI output**: UTF-8 reconfiguration of stdout and stderr so authored and log-derived Unicode render correctly in PowerShell.
- **Documentation**: README, setup guide, event spec, agent skill, Apache 2.0 license, and notice file.
- **Test suite** covering fold/render goldens, store concurrency, evidence verification, CLI grammar, copy-bridge apply, packaging, and encoding.
