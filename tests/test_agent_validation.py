import json
from pathlib import Path
from typing import Any

import pytest

from capsule.cli.commands.context import PREAMBLE

# The frozen Projection JSON keys as of Phase 2
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

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_DEMO_FIXTURES = [
    "demo-orders.jsonl",
    "demo-incidents.jsonl",
    "demo-sync.jsonl",
]


@pytest.fixture(params=_DEMO_FIXTURES)
def fixture_repo(request: Any, tmp_path: Path) -> Path:
    """Provides a temp repo seeded from a committed demo fixture log."""
    fixture_name = request.param
    source_log = _FIXTURES_DIR / fixture_name

    if not source_log.exists():
        pytest.fail(f"Missing fixture log: {fixture_name}")

    dest_repo = tmp_path / fixture_name.removesuffix(".jsonl")
    dest_capsule = dest_repo / ".capsule"
    dest_capsule.mkdir(parents=True)
    (dest_capsule / "log.jsonl").write_bytes(source_log.read_bytes())
    return dest_repo


def test_ta1_load_json(invoke_main: Any, fixture_repo: Any) -> None:
    """T-A1: load --format json."""
    res = invoke_main(["--repo", str(fixture_repo), "--format", "json", "load"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)

    # Assert exact frozen keys
    assert set(payload.keys()) == FROZEN_PROJECTION_KEYS

    # Assert event_count > 0 and objective present
    assert payload["event_count"] > 0
    assert payload["objective"]
    assert isinstance(payload["objective"], str)
    assert payload["objective"].strip() != ""


def test_ta2_load_text(invoke_main: Any, fixture_repo: Path) -> None:
    """T-A2: load (text)."""
    res = invoke_main(["--repo", str(fixture_repo), "load"])
    assert res.exit_code == 0
    text = res.stdout

    # Objective one line (not char-per-line). Find the Objective: line and the next line
    lines = text.splitlines()
    obj_idx = lines.index("Objective:")
    assert obj_idx != -1
    obj_body = lines[obj_idx + 1]
    assert len(obj_body) > 1  # Assuming it's a full string, not one character

    # Open Work / Next Steps and Recent Activity
    assert "Open Work / Next Steps:" in text
    assert "Recent Activity:" in text


def test_ta3_context(invoke_main: Any, fixture_repo: Path) -> None:
    """T-A3: context."""
    res = invoke_main(["--repo", str(fixture_repo), "context"])
    assert res.exit_code == 0
    text = res.stdout

    assert "Recent Activity:" in text
    assert PREAMBLE in text


def test_ta4_record_progress(invoke_main: Any, fixture_repo: Path) -> None:
    """T-A4: record progress then load --format json."""
    res_before = invoke_main(["--repo", str(fixture_repo), "--format", "json", "load"])
    count_before = json.loads(res_before.stdout)["event_count"]

    res_rec = invoke_main(
        ["--repo", str(fixture_repo), "record", "progress", "--note", "Test harness progress"]
    )
    assert res_rec.exit_code == 0

    res_after = invoke_main(["--repo", str(fixture_repo), "--format", "json", "load"])
    count_after = json.loads(res_after.stdout)["event_count"]

    assert count_after == count_before + 1


def test_ta5_apply_idempotency(invoke_main: Any, fixture_repo: Path) -> None:
    """T-A5: apply idempotency."""
    patch = {
        "version": "capsule-patch/v0",
        "events": [
            {"t": "progress", "id": "harness-progress-1", "note": "Harness applied patch progress"}
        ],
    }
    patch_text = f"```capsule-patch\n{json.dumps(patch)}\n```"

    res_first = invoke_main(["--repo", str(fixture_repo), "apply"], input=patch_text)
    assert res_first.exit_code == 0
    assert (
        "Applied 1 new event" in res_first.stdout
        or "Applied 1" in res_first.stderr
        or "applied" in res_first.stdout.lower()
        or "applied" in res_first.stderr.lower()
    )

    res_second = invoke_main(["--repo", str(fixture_repo), "apply"], input=patch_text)
    assert res_second.exit_code == 0
    # Second should skip due to idempotency
    assert "skipped" in res_second.stdout.lower() or "skipped" in res_second.stderr.lower()
