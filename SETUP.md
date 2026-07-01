# Setup and Usage

This guide covers installation, initialization, daily usage, and troubleshooting for the `capsule` CLI.

## Requirements

- Python 3.11 or newer
- A Git repository is recommended

## Install

Context Capsules is not on PyPI yet. Install from a local checkout for now.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
capsule --version
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
capsule --version
```

If `capsule` is not on your `PATH`, use `python -m capsule` as a drop-in replacement.

## Initialize a Repository

Run this once inside the target repo:

```bash
capsule init
```

This creates:

```text
.capsule/
  log.jsonl
  capsule.md
  .lock
```

Initialization options:

- `--draft git`: derive the first intent from recent commits
- `--draft llm`: use an OpenAI-compatible BYO-key model
- `--draft none`: start with an empty capsule
- `--force`: initialize again without deleting the log

## Core Commands

### Read the current state

```bash
capsule load
```

### View the rendered capsule

```bash
capsule show
```

### Record intent

```bash
capsule record intent --objective "Ship the public OSS launch" --constraint "No network calls in the core path" --acceptance "README and community files are production-ready"
```

### Record a decision

```bash
capsule record decision --decision "Use append-only JSONL for the event log" --rationale "It is diffable, durable, and easy to validate" --evidence file:src/capsule/store/store.py
```

### Record a question and resolution

```bash
capsule record question --question "Should this repo publish to TestPyPI before PyPI?"
capsule record resolution --closes <question-id> --answer "Yes, use TestPyPI first."
```

### Record progress

```bash
capsule record progress --note "Cross-platform CI and packaging smoke tests are green" --evidence test:tests/test_packaging.py::test_version_matches_metadata
```

### Track task lifecycle

```bash
capsule task start --task-id launch-docs --objective "Polish OSS launch surface"
capsule task end --task-id launch-docs --outcome completed --summary "Docs, templates, and workflows updated"
```

### Inspect history and health

```bash
capsule log --limit 20
capsule doctor
```

### Browser-only tools

```bash
capsule context --clip
capsule apply --clip
```

## Recommended Daily Workflow

1. Start with `capsule load`.
2. Work normally.
3. Record consequential decisions and completed progress as you go.
4. If the task has a real handoff boundary, wrap it with `capsule task start` and `capsule task end`.
5. End with `capsule show` or `capsule log --limit 10` if you want a quick review.

## JSON Output

Use `--format json` for scripts and agent integrations:

```bash
capsule --format json load
capsule --format json doctor
capsule --format json log --limit 5
```

## Development Install

If you are contributing to this repository itself:

```bash
python -m pip install -e .[dev]
ruff check .
ruff format --check .
mypy
pytest
```

## Next Docs

- `README.md` for the high-level project overview
- `docs/TROUBLESHOOTING.md` for common problems
- `docs/RELEASING.md` for the current maintainer release flow
