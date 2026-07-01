import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from capsule.cli.app import _configure_output_encoding
from capsule.engine.events import Event


def test_te1_no_pythonutf8_subprocess(tmp_path: Path) -> None:
    """T-E1: no-PYTHONUTF8 subprocess.

    Runs context with an env that specifically lacks PYTHONUTF8.
    Ensures that authored ASCII punctuation and log-derived non-ASCII
    characters survive the trip and are correctly output as UTF-8,
    not U+FFFD (replacement character).
    """
    capsule_dir = tmp_path / ".capsule"
    capsule_dir.mkdir()
    log_path = capsule_dir / "log.jsonl"

    # We include some non-ASCII in the objective (em-dash, emoji, accented char)
    # The PREAMBLE has ASCII clean text now.
    events = [
        Event(
            t="intent",
            id="ev1",
            at="2024-01-01T00:00:00Z",
            by="alice",
            objective="Objective with em-dash \u2014 and unicode \u00e9.",
        )
    ]
    with log_path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.to_jsonl() + "\n")

    env = os.environ.copy()
    # explicitly remove PYTHONUTF8 to test our _configure_output_encoding
    env.pop("PYTHONUTF8", None)

    # Use python -m capsule to run in subprocess
    result = subprocess.run(
        [sys.executable, "-m", "capsule", "--repo", str(tmp_path), "context"],
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0

    # We decode strictly as utf-8. If it wasn't utf-8, this might fail or produce U+FFFD
    stdout_str = result.stdout.decode("utf-8")
    stderr_str = result.stderr.decode("utf-8")

    # Assert no replacement characters were generated
    assert "\ufffd" not in stdout_str
    assert "\ufffd" not in stderr_str

    # Check that our non-ASCII string survived exactly
    assert "Objective with em-dash \u2014 and unicode \u00e9." in stdout_str
    # Check that ASCII preamble is present
    assert "You are continuing work on a project" in stdout_str


def test_te2_reconfigure_absent_noop(monkeypatch: Any) -> None:
    """T-E2: reconfigure-absent no-op."""
    # io.StringIO has no `reconfigure` method
    mock_stdout = io.StringIO()
    mock_stderr = io.StringIO()

    monkeypatch.setattr(sys, "stdout", mock_stdout)
    monkeypatch.setattr(sys, "stderr", mock_stderr)

    # This must not raise an error
    _configure_output_encoding()

    # And the streams must still be usable
    print("test stdout", file=sys.stdout)
    print("test stderr", file=sys.stderr)

    assert "test stdout" in mock_stdout.getvalue()
    assert "test stderr" in mock_stderr.getvalue()
