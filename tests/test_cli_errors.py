from typing import Any
from unittest.mock import patch

from capsule.engine.errors import CorruptLogLine, LockTimeout
from capsule.exit_codes import ExitCode


def test_tf8_engine_errors_exit_codes(invoke_main: Any, tmp_path: Any) -> None:
    """T-F8, T-M1: force engine errors -> exact code + actionable message."""
    invoke_main(["--repo", str(tmp_path), "init"])

    # Force LockTimeout
    with patch("capsule.engine.engine.capsule_lock") as mock_lock:
        mock_lock.side_effect = LockTimeout("mock timeout")
        res_lock = invoke_main(["--repo", str(tmp_path), "record", "progress", "--note", "n"])
    assert res_lock.exit_code == ExitCode.LOCK_TIMEOUT
    assert "mock timeout" in res_lock.stderr

    # Force CorruptLogLine (on read during record)
    with patch("capsule.engine.engine.Store.read_events") as mock_read:
        mock_read.side_effect = CorruptLogLine("mock corrupt")
        res_corrupt = invoke_main(["--repo", str(tmp_path), "record", "progress", "--note", "n"])
    assert res_corrupt.exit_code == ExitCode.CORRUPT_LOG
    assert "mock corrupt" in res_corrupt.stderr


def test_tf9_verified_false_keeps_exit_0(invoke_cli: Any, tmp_path: Any) -> None:
    """T-F9: verified:false keeps exit 0."""
    invoke_cli(["--repo", str(tmp_path), "init"])

    # Missing local evidence remains data, not an error.
    res = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "decision",
            "--decision",
            "d",
            "--rationale",
            "r",
            "--evidence",
            "file:f.py",
        ]
    )
    assert res.exit_code == 0
    assert "verified=false" in res.stdout
