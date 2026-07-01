# Governance

Context Capsules is an independent open-source project created and currently maintained by Yash Shah. This document describes how decisions are made, who makes them, and how the project evolves.

## Principles

Governance follows the project's technical values:

- **Minimize complexity.** Governance overhead should be proportional to project size. We are a small project; we use lightweight processes.
- **Transparency.** Decisions happen in public (GitHub issues, PRs, and Discussions).
- **Reversibility.** Prefer decisions that can be walked back. Irreversible commitments — especially schema changes and new dependencies — get extra scrutiny.
- **Local-first and open.** The project will remain Apache 2.0, local-first, and zero-telemetry. These are not negotiable.
- **Single-maintainer for now.** Yash Shah is currently the sole maintainer and final decision-maker for the project.

## Roles

### Contributor

Anyone who opens an issue, submits a PR, participates in a Discussion, or improves documentation. No formal process — just participate.

### Committer

A contributor who has landed multiple pull requests and demonstrated understanding of the project's principles. Committers can review and approve pull requests but cannot merge to `main` without maintainer sign-off during the early project phase.

Committer status is granted by the maintainer after a track record of quality contributions. There is no formal application.

### Maintainer

The maintainer can merge to `main`, cut releases, manage issues and labels, and make binding project decisions. The maintainer is responsible for upholding the project's invariants and this governance document.

**Current maintainer:**

| Name | GitHub | Since |
| ---- | ------ | ----- |
| Yash Shah | [@yashshah-ct](https://github.com/yashshah-ct) | 2026-06 (project founder) |

### Additional maintainers

There is no active expansion path right now. If the project grows to the point where additional maintainers are needed, Yash Shah may appoint them based on sustained, high-quality contributions, strong judgment, and alignment with the project's values.

## Decision making

### Everyday decisions (patches, docs, small features)

A single maintainer reviews and merges. No formal process beyond CI green and a look at the invariants.

### Significant changes (new commands, new dependencies, schema changes)

Require a GitHub issue describing the change and its trade-offs, at least one week of open comment, and explicit maintainer sign-off. The issue serves as the ADR (architecture decision record).

### Breaking schema changes

Require a dedicated [spec change issue](https://github.com/CognitivTrust/context-capsules/issues/new?template=spec_change.yml), a two-week comment period, explicit approval from the maintainer, and a conformance test update.

### Governance changes

Changes to this document require a PR, a two-week comment period, and approval from the maintainer.

## Project scope

The scope of Context Capsules V1 is fixed: a local-first, CLI-first decision log stored in-repo.

## Relationship to CognitivTrust

Context Capsules was created by Yash Shah as part of the CognitivTrust project. The OSS repository is independently licensed (Apache 2.0), and the open-source project operates by this governance document independently of any commercial work.

## Conflict resolution

If contributors disagree on a technical decision, the discussion happens in the relevant GitHub issue or PR. The maintainer has the final say after a good-faith attempt to incorporate feedback. If the complaint concerns the maintainer, report it privately to conduct@cognitivtrust.com rather than raising it in public.

## Amendments

This is a living document. It will be updated as the project grows. All changes are made by PR and logged in the git history.
