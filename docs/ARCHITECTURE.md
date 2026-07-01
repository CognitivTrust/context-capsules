# Architecture

This document describes the internal structure of Context Capsules, its design boundaries, and the reasoning behind them. It is written for contributors and tool authors.

## Mental model

Context Capsules is a **source of truth for project reasoning**, implemented as an **append-only log of typed events** stored as a plain file in the repo. Everything in the implementation follows from that sentence.

The log is the only source of truth. The Markdown render is derived. The CLI is a thin façade. The engine owns correctness.

## Repository layout

```
src/capsule/
  __init__.py          # version from importlib.metadata
  __main__.py          # python -m capsule entry point
  exit_codes.py        # typed exit code enum (shared by CLI and tests)
  redaction.py         # key/secret redaction for --verbose output

  cli/
    app.py             # argument parsing, global flags, dispatch
    formatting.py      # Rich-style terminal output helpers
    summary.py         # capsule load / show summary renderer
    commands/
      init.py          # capsule init
      load.py          # capsule load
      show.py          # capsule show
      record.py        # capsule record intent|decision|question|resolution|progress
      log.py           # capsule log
      task.py          # capsule task start|end
      context.py       # capsule context (web copy-bridge emitter)
      apply.py         # capsule apply (web copy-bridge ingestor)
      doctor.py        # capsule doctor
    edge/
      clipboard.py     # system clipboard read/write (OS-specific, CLI edge only)
      drafter.py       # BYO-key LLM drafter for capsule init (CLI edge only)
      evidence.py      # evidence verifier registry and CLI glue
      git.py           # git log reader for --draft git (CLI edge only)
      patch.py         # CAPSULE-PATCH block parser

  engine/
    engine.py          # CapsuleEngine: high-level operations (init, record, fold, render)
    schema.py          # event schema validation and normalization
    events.py          # typed event dataclasses (frozen)
    fold.py            # projection: log -> current state
    render.py          # current state -> Markdown
    errors.py          # typed errors: SchemaError, CorruptLogLine, ...
    verify.py          # existence-only evidence verification

  store/
    store.py           # CapsuleStore: atomic append, lock, read, path management
    lock.py            # cross-platform advisory lock (portalocker)
    paths.py           # .capsule/ layout constants
```

## Layer boundaries

```
┌─────────────────────────────────────────────────────┐
│                   CLI (cli/)                         │
│  arg parsing · exit codes · formatting · --format   │
│  edge/: clipboard · drafter · git · patch           │
└──────────────────┬──────────────────────────────────┘
                   │  calls
┌──────────────────▼──────────────────────────────────┐
│               Engine (engine/)                       │
│  init · record · fold · render · verify · schema    │
│  ZERO network I/O  ·  ZERO tool-specific logic       │
└──────────────────┬──────────────────────────────────┘
                   │  calls
┌──────────────────▼──────────────────────────────────┐
│               Store (store/)                         │
│  atomic append  ·  lock  ·  read  ·  paths          │
└─────────────────────────────────────────────────────┘
```

**The CLI layer** handles user-facing concerns: argument parsing, output formatting, clipboard access, git history reading, LLM drafting, and CAPSULE-PATCH ingestion. It knows about specific tools and operating systems. It calls the engine.

**The engine layer** owns data correctness: schema validation, folding events into a projection, rendering the projection to Markdown, and evidence verification. It is pure logic with no network calls and no tool-specific knowledge. It calls the store.

**The store layer** owns I/O safety: reading the log (including torn-line recovery), atomic appends, cross-platform locking, and path management. It knows nothing about event semantics.

This layering is enforced by convention and tested by `tests/test_no_network.py` (which confirms no network socket is opened during any store or engine operation).

## Core data flow

### Write path (e.g. `capsule record decision`)

1. CLI parses args, resolves evidence refs, calls `engine.record_decision(...)`.
2. Engine validates the event dict against the schema (`schema.validate_event`), producing a typed `Decision` dataclass.
3. Engine calls `store.append(event)` under the advisory lock.
4. Store serializes the event to compact JSONL, atomically appends to `log.jsonl`, then calls `engine.render(fold(log))` to regenerate `capsule.md` atomically.
5. Store releases the lock. Engine returns the event. CLI prints confirmation.

### Read path (e.g. `capsule load`)

1. CLI calls `engine.fold()`.
2. Engine calls `store.read_log()`, which reads `log.jsonl` line-by-line.
3. If the last line is torn (incomplete JSON from a crash), it is quarantined: moved to `.capsule/quarantine/` and a warning is surfaced. The rest of the log is valid.
4. Engine folds valid events into a `CapsuleProjection` (current state).
5. CLI formats the projection as text or JSON and prints it.

## Append safety and crash recovery

Writes are atomic: the store writes to a temporary file and calls `os.replace()`, which is atomic on all supported platforms. A `kill -9` mid-write leaves either the old file or the new file, never a partial.

The one exception is the JSONL append itself, which cannot be made fully atomic with `os.replace` while preserving the append-only property. Instead, the store uses a CRC or length guard to detect a torn final line (a line that is not valid JSON, which can happen if a process is killed between `write()` and `flush()`). A torn line is quarantined rather than corrupting subsequent reads or writes.

## Evidence verification

The verifier registry maps an evidence `kind` to a verifier function. Built-in verifiers:

| Kind | Check |
| ---- | ----- |
| `file` | `Path(ref).exists()` relative to the repo root |
| `commit` | `git cat-file -e <ref>` |
| `test` | The test file cited in the `ref` exists on disk |
| `url` | Syntax validation only (no network request) |

`verified` on an event is the AND of all evidence checks. `verified: false` is data — the engine never raises because evidence is missing. Adding a new verifier is a matter of registering a function in the registry; no engine changes required.

## Forward compatibility

The schema uses a strict allowed-field list per event type. Unknown top-level fields, unknown `by` sub-fields, and unknown evidence-ref fields are preserved in insertion order and round-tripped unchanged. This means a log written by a newer version of the tool can be read by an older version without data loss.

## The web copy-bridge

`capsule context` emits a structured Markdown block containing the current capsule state. The user pastes it into a browser-based AI tool (ChatGPT, Claude.ai). The AI tool responds with a `CAPSULE-PATCH` block. `capsule apply` parses the block and appends the events it contains. This is the only way browser-only tools can interact with the capsule without a CLI integration. The clipboard is accessed via OS-native commands at the CLI edge, never in the engine.

## What the engine does NOT do

- No network I/O of any kind.
- No knowledge of specific AI tools, IDEs, or shell environments.
- No reading of `capsule.md` as truth (it is write-only from the engine's perspective).
- No semantic or behavioral verification of evidence content.
- No selection layer, slug routing, or workstream-specific semantics in the current implementation.
