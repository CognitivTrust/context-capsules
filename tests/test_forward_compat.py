import json
from typing import Any


def test_ts1_forward_compat_round_trip(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-S1: round-trip & unknown-field preservation."""
    invoke_cli(["--repo", str(tmp_path), "init"])

    # We'll inject an event with an unknown field via apply
    patch_text = """```capsule-patch
    {"version": "capsule-patch/v0", "events": [
        {"id": "p1", "t": "progress", "note": "n", "unknown_alien_field": "hello"}
    ]}
    ```"""

    res = invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text)

    assert res.exit_code == 0

    # Read the raw log and check it
    log_text = (tmp_path / ".capsule" / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_text) == 1

    event_obj = json.loads(log_text[0])
    assert event_obj["unknown_alien_field"] == "hello"

    # Through load json (raw events in log command are exact objects)
    res_log = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    payload = json.loads(res_log.stdout)
    assert payload[-1]["unknown_alien_field"] == "hello"
