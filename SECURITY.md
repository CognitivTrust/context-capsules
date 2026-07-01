# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

Only the latest released version receives security fixes. If you are on an older version, upgrade first.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Please report security issues privately so Yash Shah, the project's sole maintainer, can assess and patch before public disclosure.

**Preferred channel:** Email **security@cognitivtrust.com** with the subject line `[context-capsules] Security Report`. If you do not receive a response within 72 hours, follow up by directly messaging [@yashshah-ct](https://github.com/yashshah-ct) on GitHub.

**What to include:**

- A clear description of the vulnerability and its potential impact.
- Steps to reproduce or a minimal proof-of-concept.
- The version(s) affected.
- Any suggested mitigations (optional but appreciated).

Please give a reasonable disclosure window (typically 90 days) before making the issue public. The maintainer will keep you informed of progress and credit you in the release notes unless you prefer to remain anonymous.

## Threat model

Context Capsules is a **local-first CLI tool**. Understanding its threat model helps set accurate expectations about what is and is not a security concern:

**In scope:**

- **Path traversal / symlink escape** — evidence refs or file paths that could escape the repo root.
- **Lock integrity** — advisory lock bypass that could corrupt the append-only log.
- **Torn-line injection** — crafted log content that survives quarantine and corrupts state.
- **BYO-key secret handling** — leakage of API keys read from env or keyring.
- **Supply-chain** — a dependency (`portalocker`) that introduces a vulnerability.

**Out of scope (by design):**

- Network-based attacks against the core engine. The core does **zero network I/O**. There is nothing to attack remotely.
- Authentication or authorization. The capsule is owned by whoever can write to the repo — exactly like the code itself.
- Multi-tenancy. There is no server, no accounts, and no session isolation to maintain.
- Semantic validation of evidence content. The tool only checks existence, never reads or executes cited files.

## Security design notes

- The core engine has no network code. The only optional network use is a BYO-key LLM drafter in `capsule init`, which is an opt-in CLI-edge feature that reads keys from the environment or system keyring and never persists them.
- All durable writes are atomic (tmp file + `os.replace`). A crash or kill mid-write leaves either the old file or the new one, never a partial.
- File locking uses `portalocker` for cross-platform advisory locking — never POSIX-only `fcntl`.
- Evidence references are treated strictly as data. They are never executed, evaluated, or passed to a shell.
