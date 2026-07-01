"""Guard committed capsule fixtures against schema drift.

The engine validates every event before it appends, so the engine itself can
never write a schema-invalid line. The only way an invalid line lands in the
repo is an external write: a hand-edited or generated fixture. These tests make
that failure mode loud and located at test/CI time instead of surfacing later
as a runtime "corrupt log" mystery.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from capsule.engine.schema import from_obj

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
COMMITTED_FIXTURE_LOGS = sorted(FIXTURES_DIR.glob("*.jsonl"))


def test_committed_fixture_logs_are_present() -> None:
    assert COMMITTED_FIXTURE_LOGS, "expected at least one committed *.jsonl fixture"


@pytest.mark.parametrize(
    "log_path",
    COMMITTED_FIXTURE_LOGS,
    ids=lambda path: path.name,
)
def test_committed_fixture_log_is_schema_valid(log_path: Path) -> None:
    raw = log_path.read_text(encoding="utf-8")
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{log_path}: line {lineno} is not valid JSON: {exc}")
        try:
            from_obj(obj)
        except Exception as exc:  # noqa: BLE001 - surface any validation failure with location
            pytest.fail(f"{log_path}: line {lineno} violates the event schema: {exc}")
