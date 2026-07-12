import json
from pathlib import Path
from typing import Any

# The frozen JSON keys as of Phase 2
FROZEN_PROJECTION_KEYS = {
    "objective",
    "current_understanding",
    "constraints",
    "invariants",
    "acceptance",
    "decisions",
    "open_questions",
    "open_tasks",
    "resolved_questions",
    "progress",
    "event_count",
}

FROZEN_CONTEXT_KEYS = {
    "copied",
    "block",
}


def test_tb1_commands_unregistered(invoke_main: Any) -> None:
    """T-B1: commands unregistered (diff, revert, stats, status)."""
    import pytest

    for cmd in ["diff", "revert", "stats", "status"]:
        with pytest.raises(SystemExit) as excinfo:
            invoke_main([cmd])
        assert excinfo.value.code == 2, f"Command {cmd} should be unregistered"


def test_tb4_json_freeze(invoke_main: Any, tmp_path: Path) -> None:
    """T-B4: JSON freeze."""
    invoke_main(["--repo", str(tmp_path), "init"])

    res_load = invoke_main(["--repo", str(tmp_path), "--format", "json", "load"])
    assert res_load.exit_code == 0
    load_payload = json.loads(res_load.stdout)
    assert set(load_payload.keys()) == FROZEN_PROJECTION_KEYS
    assert "recent_activity" not in load_payload
    assert "open_work" not in load_payload

    res_ctx = invoke_main(["--repo", str(tmp_path), "--format", "json", "context"])
    assert res_ctx.exit_code == 0
    ctx_payload = json.loads(res_ctx.stdout)
    assert set(ctx_payload.keys()) == FROZEN_CONTEXT_KEYS
