# Troubleshooting

Run `capsule doctor` first. It performs a local health check and surfaces the most common problems automatically.

---

## Installation problems

### `capsule: command not found` (or `capsule is not recognized`)

The virtualenv's `bin/` (macOS/Linux) or `Scripts/` (Windows) directory is not on your `PATH`.

**Fix:** Use `python -m capsule` as a drop-in replacement for any `capsule` command, or ensure the venv is activated:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### `python: command not found` / wrong Python version

On macOS, the system Python is often 3.9 or older. Context Capsules requires 3.11+.

**Fix:** Install a newer Python via Homebrew (`brew install python@3.12`) or `pyenv`, then create the venv with that version:

```bash
python3.12 -m venv .venv
```

---

## Initialization problems

### `capsule init` fails with "already initialized"

A `.capsule/` directory is already present at the target path.

**Fix:** Use `capsule init --force` to re-initialize. This preserves the existing log; it does not delete history.

---

## Write / lock problems

### `LOCK_TIMEOUT` (exit code 5)

Another process holds the capsule lock. This usually means a previous `capsule` command crashed while holding the lock.

**Fix:** Remove the stale lock file and retry:

```bash
# macOS / Linux
rm .capsule/.lock

# Windows PowerShell
Remove-Item .capsule\.lock
```

If the problem recurs, run `capsule doctor` to check lock health.

### Events appear to have been written but `capsule load` doesn't show them

Most likely `capsule.md` is stale. The render is regenerated on every write; if a write was interrupted, it may be out of date.

**Fix:** Force a render by running `capsule show` (which re-folds and re-renders the log), or `capsule doctor` (which checks consistency).

---

## Read / schema problems

### `SchemaError` when loading the capsule

A log line fails schema validation. This can happen if `log.jsonl` was hand-edited or written by a non-conformant tool.

**Fix:** Run `capsule doctor` to identify the offending line. The torn-line quarantine handles incomplete lines automatically; a schema-invalid line requires manual review. Back up the file and inspect the line reported in the error.

### `CORRUPT_LOG` (exit code 6)

The final line of `log.jsonl` is not valid JSON (torn line from a crash).

**Fix:** The next write automatically quarantines the torn line to `.capsule/quarantine/`. Alternatively, run `capsule doctor` to confirm and manually remove the torn line if you prefer not to wait for the next write.

### `verified: false` on a decision I just recorded

The evidence reference you cited couldn't be confirmed to exist. This is not an error — it's data.

Common reasons:
- The file path in `--evidence file:...` is misspelled or relative to the wrong directory. Run from the repo root.
- The commit hash in `--evidence commit:...` doesn't exist in the local repo (e.g., it's on a remote branch not yet fetched).
- A `url:` ref is never network-checked; it is always syntax-validated only.

**Fix:** Re-record with a corrected reference. The old event is preserved in history.

---

## Output / encoding problems

### Garbled characters or `UnicodeEncodeError` in PowerShell

Windows PowerShell's default code page is often not UTF-8.

**Fix:** The CLI reconfigures stdout/stderr to UTF-8 on startup. If you see garbled output, ensure you are running a recent version of the package. If the issue persists, set the code page manually:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Or set the environment variable before running:

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

---

## Evidence verification

### `EvidenceUnreadable` (exit code 7)

The engine could not read the repo root to check evidence (usually a permissions problem).

**Fix:** Confirm you are running `capsule` from inside the repo, or pass the correct `--repo <path>`.

---

## Still stuck?

1. Run `capsule doctor` and copy the full output.
2. Check [docs/FAQ.md](FAQ.md).
3. Search [GitHub Issues](https://github.com/CognitivTrust/context-capsules/issues).
4. Open a [GitHub Discussion](https://github.com/CognitivTrust/context-capsules/discussions/categories/q-a) with the doctor output, OS, Python version, and `capsule --version`.
