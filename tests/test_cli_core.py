import json
from pathlib import Path
from typing import Any

from capsule.engine.schema import from_obj


def test_cli_round_trip(invoke_cli: Any, tmp_path: Path) -> None:
    # 33. init -> record -> load/show round-trip.

    # 1. init
    res_init = invoke_cli(["--repo", str(tmp_path), "init"])
    assert res_init.exit_code == 0

    # 2. record
    res_rec = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "decision",
            "--decision",
            "D",
            "--rationale",
            "R",
            "--evidence",
            "file:a.py",
        ]
    )
    assert res_rec.exit_code == 0
    assert "Recorded decision" in res_rec.stdout
    assert "verified=false" in res_rec.stdout

    # 3. load json
    res_load = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    assert res_load.exit_code == 0
    payload = json.loads(res_load.stdout)
    assert len(payload["decisions"]) == 1
    assert payload["decisions"][0]["decision"] == "D"
    assert payload["decisions"][0]["verified"] is False

    # 4. show
    res_show = invoke_cli(["--repo", str(tmp_path), "show"])
    assert res_show.exit_code == 0
    assert "## Decisions" in res_show.stdout
    assert "- D" in res_show.stdout

    # Check on-disk
    log_path = tmp_path / ".capsule" / "log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["t"] == "decision"
    assert obj["decision"] == "D"

    # Stamped line serialization verification
    event = from_obj(obj)
    assert lines[0] == event.to_jsonl()


def test_cli_error_codes(invoke_cli: Any, tmp_path: Path) -> None:
    # 34. CLI error codes.

    # No capsule
    res_load = invoke_cli(["--repo", str(tmp_path), "load"])
    assert res_load.exit_code == 3
    assert "run `capsule init`" in res_load.stderr

    # Schema error (dangling closes)
    invoke_cli(["--repo", str(tmp_path), "init"])
    res_rec = invoke_cli(
        ["--repo", str(tmp_path), "record", "resolution", "--closes", "bogus", "--answer", "x"]
    )
    assert res_rec.exit_code == 4
    assert "unknown question id" in res_rec.stderr
