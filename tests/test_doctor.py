import json
from pathlib import Path
from typing import Any

from capsule.cli.commands.doctor import STALE_UNDERSTANDING_THRESHOLD
from capsule.engine.events import Event


def test_doctor_empty_repo_exits_zero(invoke_cli: Any, tmp_path: Path) -> None:
    res = invoke_cli(["--repo", str(tmp_path), "doctor"])

    assert res.exit_code == 0
    assert "Capsule exists: False" in res.stdout


def test_doctor_reports_event_count(invoke_cli: Any, tmp_path: Path) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    invoke_cli(["--repo", str(tmp_path), "record", "progress", "--note", "done"])

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["capsule_exists"] is True
    assert payload["event_count"] == 1
    assert payload["render_exists"] is True


def test_doctor_json_shape(invoke_cli: Any, tmp_path: Path) -> None:
    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert set(payload) == {
        "repo",
        "python",
        "capsule_exists",
        "event_count",
        "torn",
        "render_exists",
        "lock_exists",
        "git",
        "warnings",
    }


def test_doctor_reports_schema_violation(invoke_cli: Any, tmp_path: Path) -> None:
    # A schema-invalid line (valid JSON, missing required fields) is reported as a
    # 'schema' problem, not as corruption, and doctor itself still exits 0.
    invoke_cli(["--repo", str(tmp_path), "init"])
    log = tmp_path / ".capsule" / "log.jsonl"
    with open(log, "ab") as handle:
        handle.write(b'{"t":"intent","id":"x"}\n')

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["event_count"] is None
    assert payload["log_error_kind"] == "schema"
    assert "log_error" in payload


def test_doctor_reports_corrupt_log(invoke_cli: Any, tmp_path: Path) -> None:
    # Structurally broken bytes are reported as 'corrupt', distinct from a schema problem.
    invoke_cli(["--repo", str(tmp_path), "init"])
    log = tmp_path / ".capsule" / "log.jsonl"
    with open(log, "ab") as handle:
        handle.write(b'{"t":"intent","id":"1","at":"now","objective":"o"}\n')
        handle.write(b"{bad json\n")

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["event_count"] is None
    assert payload["log_error_kind"] == "corrupt"


def test_doctor_warns_when_understanding_never_set(invoke_cli: Any, tmp_path: Path) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    _append_events(
        tmp_path,
        [
            Event(
                t="decision",
                id="d1",
                at="2024-01-01T00:00:00Z",
                by="alice",
                decision="Use bounded load text",
                rationale="Agent context stays smaller",
            ),
            Event(
                t="progress",
                id="p1",
                at="2024-01-01T00:01:00Z",
                by="alice",
                note="Implemented the formatter path",
            ),
        ],
    )

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    warning = payload["warnings"][0]
    assert warning.startswith(
        "current_understanding has never been set, but the log has 2 decision/progress events"
    )
    assert "--current-understanding so agents inherit current state" in warning


def test_doctor_warns_when_understanding_is_stale(invoke_cli: Any, tmp_path: Path) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    events = [
        Event(
            t="intent",
            id="intent1",
            at="2024-01-01T00:00:00Z",
            by="alice",
            objective="Ship the feature",
            current_understanding=("Formatter work is in progress.",),
        )
    ]
    for index in range(STALE_UNDERSTANDING_THRESHOLD):
        event_id = f"e{index}"
        at = f"2024-01-01T00:0{index + 1}:00Z"
        if index % 2 == 0:
            events.append(
                Event(
                    t="decision",
                    id=event_id,
                    at=at,
                    by="alice",
                    decision=f"Decision {index}",
                    rationale=f"Rationale {index}",
                )
            )
        else:
            events.append(
                Event(
                    t="progress",
                    id=event_id,
                    at=at,
                    by="alice",
                    note=f"Progress {index}",
                )
            )
    _append_events(tmp_path, events)

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    warning = payload["warnings"][0]
    assert warning.startswith(
        "current_understanding may be stale: last set by intent1 at 2024-01-01T00:00:00Z, "
        f"but {STALE_UNDERSTANDING_THRESHOLD} decision/progress events recorded since"
    )
    assert "refresh it by recording a new intent with --current-understanding" in warning


def test_doctor_skips_staleness_warning_for_fresh_understanding(
    invoke_cli: Any, tmp_path: Path
) -> None:
    invoke_cli(["--repo", str(tmp_path), "init"])
    _append_events(
        tmp_path,
        [
            Event(
                t="intent",
                id="intent1",
                at="2024-01-01T00:00:00Z",
                by="alice",
                objective="Ship the feature",
                current_understanding=("Formatter work is done.",),
            ),
            Event(
                t="decision",
                id="d1",
                at="2024-01-01T00:01:00Z",
                by="alice",
                decision="Use bounded load text",
                rationale="Agent context stays smaller",
            ),
            Event(
                t="progress",
                id="p1",
                at="2024-01-01T00:02:00Z",
                by="alice",
                note="Implemented the formatter path",
            ),
        ],
    )

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "doctor"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert all("current_understanding" not in warning for warning in payload["warnings"])


def _append_events(repo: Path, events: list[Event]) -> None:
    log_path = repo / ".capsule" / "log.jsonl"
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        for event in events:
            handle.write(event.to_jsonl() + "\n")
