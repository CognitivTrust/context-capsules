---
name: context-capsules
description: Use context-capsules in any project that has a .capsule/ folder. Load first, record consequential decisions, capture meaningful progress, use task lifecycle for explicit handoffs, surface open questions, and use the web copy-bridge for browser-only tools.
---

# Context Capsules Agent Skill

This project uses **Context Capsules**: a local, append-only decision log stored in `.capsule/log.jsonl`. Every consequential decision, meaningful unit of progress, open question, and explicit task handoff is recorded there through the `capsule` CLI.

Use `.capsule/` in this working tree. Never edit `.capsule/log.jsonl` directly.

When you parse output programmatically, pass `--format json` (the default is human-readable `text`). Every command accepts it.

## 1. Start every task with `capsule load`

If this working tree has no `.capsule/` yet, initialize it and seed the first intent yourself from recent history:

```bash
capsule init
git log --oneline -n 20
capsule record intent --by "<tool-name>" --objective "<from recent history>" --current-understanding "<what the repo appears to be>"
```

Either way, run:

```bash
capsule load
```

Treat the result as the current source of truth for objective, constraints, invariants, decisions, open questions, progress, and open tasks. Use `capsule show` for the full render and `capsule log` (optionally `--limit N`) for raw history.

## 2. Record consequential decisions

Use `capsule record decision` when you choose an approach, set a pattern, add or remove a dependency, or settle a non-obvious trade-off.

```bash
capsule record decision   --by "<tool-name>"   --decision "<what was decided>"   --rationale "<why>"   --evidence file:<path>
```

Never invent evidence. Only cite files, commits, tests, or URLs that exist.

## 3. Record meaningful progress

Use `capsule record progress` only for completed, durable progress. It can cite evidence too.

```bash
capsule record progress   --by "<tool-name>"   --note "<what was completed>"   --evidence commit:<sha>
```

If the codebase state has materially changed, refresh the `intent` so later sessions inherit the new understanding:

```bash
capsule record intent   --by "<tool-name>"   --objective "<current objective>"   --current-understanding "<what is now known>"   --constraint "<constraint>"   --invariant "<must-not-break>"   --acceptance "<done criterion>"
```

## 4. Track explicit task lifecycle when it helps handoffs

Use task lifecycle events for bounded work that other humans or agents may resume later.

```bash
capsule task start --task-id "<task-id>" --objective "<objective>" --by "<tool-name>"
capsule task end --task-id "<task-id>" --outcome completed --summary "<summary>" --by "<tool-name>"
```

Use outcomes `completed`, `abandoned`, or `superseded`.

## 5. Surface real uncertainty as a question

```bash
capsule record question --by "<tool-name>" --question "<specific question>"
```

When answered, close it with:

```bash
capsule record resolution --by "<tool-name>" --closes <question-id> --answer "<answer>"
```

## 6. Use the web copy-bridge for browser-only tools

Before a browser session:

```bash
capsule context --clip
```

After the browser tool returns a `capsule-patch` block:

```bash
capsule apply --clip
```

Add `--dry-run` to preview which events would be applied or skipped before writing.

## 7. Guardrails

- Do not treat `verified: false` as a write failure; it is recorded data.
- Do not add network behavior anywhere in the tool.
- Do not rewrite old log entries. Corrections are new events.
- Prefer accurate, durable notes over noisy status updates.
