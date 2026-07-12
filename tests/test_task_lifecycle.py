from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from capsule.engine import ByObject, Engine, SchemaError
from capsule.engine.events import Event
from capsule.engine.fold import fold
from capsule.engine.schema import from_obj
from capsule.store.paths import CapsulePaths
from capsule.store.store import Store


def test_structured_by_round_trip_is_byte_stable(tmp_path: Path) -> None:
    line = (
        '{"t":"progress","id":"p1","at":"2026-06-29T10:00:00Z",'
        '"by":{"principal":"cursor","subagent":"core-implementer","model":"gpt-5.4-medium",'
        '"session":"s1","task":"t1","extra_field":"x"},"note":"done"}'
    )
    store = Store(CapsulePaths.for_repo(tmp_path))
    store.create()
    store.append_line(line)

    read_result = store.read_events()

    assert len(read_result.events) == 1
    assert read_result.events[0].to_jsonl() == line


def test_string_by_round_trip_is_byte_stable(tmp_path: Path) -> None:
    line = '{"t":"progress","id":"p1","at":"2026-06-29T10:00:00Z","by":"cursor","note":"done"}'
    store = Store(CapsulePaths.for_repo(tmp_path))
    store.create()
    store.append_line(line)

    read_result = store.read_events()

    assert len(read_result.events) == 1
    assert read_result.events[0].to_jsonl() == line


def test_pre_task_log_load_keeps_existing_payload_shape_plus_empty_open_tasks(
    invoke_cli: Any, tmp_path: Path
) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "intent",
            "--objective",
            "Ship it",
            "--current-understanding",
            "Known state",
            "--constraint",
            "Keep it local",
            "--invariant",
            "Append only",
            "--acceptance",
            "Tests pass",
        ]
    )
    invoke_cli(
        ["--repo", str(tmp_path), "record", "progress", "--note", "Completed migration prep"]
    )

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    payload = json.loads(res.stdout)

    assert payload["open_tasks"] == []
    without_open_tasks = dict(payload)
    del without_open_tasks["open_tasks"]
    assert without_open_tasks == {
        "objective": "Ship it",
        "current_understanding": ["Known state"],
        "constraints": ["Keep it local"],
        "invariants": ["Append only"],
        "acceptance": ["Tests pass"],
        "decisions": [],
        "open_questions": [],
        "resolved_questions": [],
        "progress": [
            {
                "id": payload["progress"][0]["id"],
                "at": payload["progress"][0]["at"],
                "by": "cli",
                "note": "Completed migration prep",
                "evidence": [],
                "verified": None,
            }
        ],
        "event_count": 2,
    }


def test_fold_task_start_then_end_clears_open_tasks() -> None:
    events = (
        Event(
            t="task_start",
            id="ts1",
            at="2026-06-29T10:00:00Z",
            by="cursor",
            task_id="task-1",
            objective="Implement ADR-0002",
        ),
        Event(
            t="task_end",
            id="te1",
            at="2026-06-29T11:00:00Z",
            by="cursor",
            closes_task="task-1",
            outcome="completed",
        ),
    )

    projection = fold(events)

    assert projection.open_tasks == ()


def test_fold_task_start_without_end_yields_open_task() -> None:
    event = Event(
        t="task_start",
        id="ts1",
        at="2026-06-29T10:00:00Z",
        by=ByObject(principal="cursor", subagent="core-implementer"),
        task_id="task-1",
        objective="Implement ADR-0002",
        for_intent="intent-1",
    )

    projection = fold((event,))

    assert projection.open_tasks == (projection.open_tasks[0],)
    assert projection.open_tasks[0].task_id == "task-1"
    assert projection.open_tasks[0].objective == "Implement ADR-0002"
    assert projection.open_tasks[0].started_at == "2026-06-29T10:00:00Z"
    assert projection.open_tasks[0].started_by == ByObject(
        principal="cursor", subagent="core-implementer"
    )
    assert projection.open_tasks[0].for_intent == "intent-1"


def test_task_end_without_matching_start_raises_schema_error(tmp_path: Path) -> None:
    engine = Engine(tmp_path)
    engine.init()

    with pytest.raises(SchemaError, match="unknown task id"):
        engine.end_task("task-missing", "completed")


@pytest.mark.parametrize(
    ("obj", "message"),
    [
        (
            {"t": "task_start", "id": "1", "at": "now", "objective": "obj"},
            "'task_id' must be a non-empty string",
        ),
        (
            {"t": "task_start", "id": "1", "at": "now", "task_id": "t1"},
            "'objective' must be a non-empty string",
        ),
        (
            {"t": "task_end", "id": "1", "at": "now", "outcome": "completed"},
            "'closes_task' must be a non-empty string",
        ),
        (
            {"t": "task_end", "id": "1", "at": "now", "closes_task": "t1", "outcome": "bogus"},
            "invalid task outcome",
        ),
        (
            {"t": "progress", "id": "1", "at": "now", "by": 123, "note": "n"},
            "'by' must be a string or object",
        ),
        (
            {"t": "progress", "id": "1", "at": "now", "by": {"subagent": "x"}, "note": "n"},
            "'by.principal' is required",
        ),
        (
            {
                "t": "progress",
                "id": "1",
                "at": "now",
                "by": {"principal": "cursor", "model": 5},
                "note": "n",
            },
            "'by.model' must be a string",
        ),
        (
            {
                "t": "progress",
                "id": "1",
                "at": "now",
                "by": {"subagent": "x", "principal": "cursor"},
                "note": "n",
            },
            "'by' object keys must be ordered",
        ),
    ],
)
def test_adr_malformed_inputs_fail(obj: dict[str, object], message: str) -> None:
    with pytest.raises(SchemaError, match=message):
        from_obj(obj)


def test_doctor_reports_open_tasks_and_exits_zero(invoke_cli: Any, tmp_path: Path) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "task",
            "start",
            "--task-id",
            "task-1",
            "--objective",
            "Implement ADR-0002",
        ]
    )
    invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "task",
            "end",
            "--task-id",
            "task-1",
            "--outcome",
            "completed",
        ]
    )

    res = invoke_cli(["--repo", str(tmp_path), "doctor"])

    assert res.exit_code == 0
    assert "Open Tasks: 0" in res.stdout


def test_cli_task_start_and_end_use_shared_task_id_and_structured_by(
    invoke_cli: Any, tmp_path: Path
) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])

    start = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "task",
            "start",
            "--task-id",
            "task-1",
            "--objective",
            "Implement ADR-0002",
            "--by-principal",
            "cursor",
            "--by-subagent",
            "core-implementer",
            "--by-model",
            "gpt-5.4-medium",
            "--by-session",
            "session-1",
        ]
    )
    end = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "task",
            "end",
            "--task-id",
            "task-1",
            "--outcome",
            "completed",
            "--summary",
            "Done",
            "--by-principal",
            "cursor",
            "--by-subagent",
            "core-implementer",
            "--by-model",
            "gpt-5.4-medium",
            "--by-session",
            "session-1",
        ]
    )

    assert start.exit_code == 0, start.stderr
    assert end.exit_code == 0, end.stderr

    log_res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    payload = json.loads(log_res.stdout)

    assert [item["t"] for item in payload] == ["task_start", "task_end"]
    assert payload[0]["task_id"] == "task-1"
    assert payload[1]["closes_task"] == "task-1"
    assert payload[0]["by"] == {
        "principal": "cursor",
        "subagent": "core-implementer",
        "model": "gpt-5.4-medium",
        "session": "session-1",
    }
    assert payload[1]["by"] == payload[0]["by"]


def test_cli_by_and_by_principal_mismatch_rejected(invoke_cli: Any, tmp_path: Path) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])

    res = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "progress",
            "--note",
            "n",
            "--by",
            "cursor",
            "--by-principal",
            "claude-code",
        ]
    )

    assert res.exit_code == 4
    assert "--by and --by-principal must match" in res.stderr
