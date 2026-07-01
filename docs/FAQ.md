# Frequently Asked Questions

## General

### What is Context Capsules?

Context Capsules is a local-first CLI tool that gives a software project a durable memory for the *why* behind its code — the decisions made, the constraints that must hold, the questions debated and settled, and the progress made. It stores this as an append-only log of typed events in `.capsule/log.jsonl` inside the repo, alongside the code.

### How is this different from a wiki, a README, or PR comments?

A wiki is written once, lives outside the code, and rots. PR comments scroll away. A README is a marketing document, not a decision log. Context Capsules records *consequential* decisions at the moment they are made, in a format that is both human-readable and machine-readable, and that travels with the repo in Git. It is the source of truth, not a summary after the fact.

### How is this different from AI "memory" features?

AI memory features remember *you* across *your* sessions in *one vendor's product*. They don't belong to the project, don't transfer between tools, and disappear when you switch models or a colleague opens the repo. Capsule data lives with the codebase, not in a vendor's product. It is readable and writable by any tool that can run a shell command.

### Is this a SaaS or cloud service?

No. There is no server, no account, no telemetry, no network call in the core path. Capsule data is stored as files alongside the code. It travels exactly like code: via Git.

### What is the one runtime dependency?

`portalocker` — for cross-platform advisory file locking. That is it. Everything else is Python standard library.

---

## Usage

### Do I need to be in a Git repo to use this?

Git is recommended but not required. Git provides free history (`git log .capsule/log.jsonl`) and sharing via pull/push. Without Git, the capsule still works; it just has no distributed history.

### What happens if two processes write to the capsule at the same time?

The store uses an advisory lock (via `portalocker`). A second writer waits for the lock to be released. If the lock is held longer than the timeout, the CLI exits with exit code `5` (`LOCK_TIMEOUT`). This is the correct behavior — it surfaces the contention rather than silently corrupting the log.

### Can I edit `log.jsonl` directly?

No. Direct edits can break the append-only guarantee, corrupt JSON structure, and break the schema. If you need to correct a record, append a new compensating event (e.g., a new `intent` that supersedes the old one). History is never rewritten.

### Can I delete old events to keep the log small?

No. Events are immutable and append-only. The log is designed to grow over the life of a project. In practice, even active projects accumulate only a few KB of events per week. If you need to start fresh, re-initialize with `capsule init --force` (which preserves the existing log and appends a new intent event).

### What does `verified: false` mean?

It means that one or more evidence references cited in an event (`file:`, `commit:`, `test:`, `url:`) could not be confirmed to exist at the time the event was recorded. This is data, not an error. Common causes: the file hasn't been created yet, the commit is on a different branch, or a URL was not checked (URL refs are syntax-validated only; no network request is made).

### How do I use the capsule with ChatGPT, Claude.ai, or other browser-based tools?

Use the web copy-bridge:

```bash
# Before the browser session — copies a context block to your clipboard
capsule context --clip

# After the browser tool responds with a CAPSULE-PATCH block — pastes it from clipboard
capsule apply --clip
```

---

## Installation

### Why isn't this on PyPI yet?

The package is in pre-release (`v0.1.0`). Once the public OSS launch is stable, it will be published as `context-capsule` on PyPI, and `pipx install context-capsule` will be the recommended install path.

### I get "capsule: command not found" after installing.

Your virtualenv `bin/` or `Scripts/` directory is probably not on `PATH`. Use `python -m capsule` as a drop-in replacement for `capsule`. Or ensure the venv is activated before running commands.

### Can I install it globally without a venv?

Use `pipx` once the package is on PyPI: `pipx install context-capsule`. `pipx` installs the tool in an isolated environment and puts the `capsule` binary on your PATH.

### What Python versions are supported?

Python 3.11 and 3.12. Python 3.10 and earlier are not supported.

---

## Schema and format

### Is the JSONL format stable?

The Capsule Event Standard is versioned (currently `v0.1.0`). The schema follows `MAJOR.MINOR.PATCH` versioning independently of the package version. Backward-compatible additions (new optional fields, new event types) get a MINOR bump. Documentation-only clarifications can use a PATCH bump. Breaking changes require a MAJOR bump, a written rationale, and approval from the current maintainer.

### Can I read the log from another programming language?

Yes. `log.jsonl` is UTF-8 compact JSON, one event per line. Any JSON library can parse it. Unknown fields should be preserved and round-tripped, not rejected.

### Can I build a tool that writes to the capsule?

Yes. The format is open. Follow the on-disk contract used by the reference implementation, append events in the canonical field order, and use an advisory lock while writing. The `capsule` CLI serves as the reference implementation.

---

## Contributing

### How do I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md). The short version: find or open an issue, branch from `main`, make the change with tests, run `ruff`, `mypy`, and `pytest`, and open a PR.

### I want to propose a change to the event schema. Where do I start?

Open a [schema change issue](https://github.com/CognitivTrust/context-capsules/issues/new?template=spec_change.yml). Read the governance rules in [GOVERNANCE.md](../GOVERNANCE.md) before proposing.
