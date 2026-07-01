import json
import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from capsule.engine.engine import Engine
from capsule.engine.errors import CapsuleError, NoCapsule, SchemaError
from capsule.engine.events import Evidence


def test_programmatic_append(tmp_path: Path) -> None:
    # 1. Programmatic append → canonical line.
    def mock_now() -> datetime:
        return datetime(2026, 6, 5, 12, 30, 0, tzinfo=UTC)

    def mock_uuid() -> str:
        return "e1"

    engine = Engine(tmp_path, now=mock_now, new_id=mock_uuid)
    engine.init()

    event = engine.record_intent(objective="Obj 1", constraints=["C1"], acceptance=[])

    # Check stamped fields
    assert event.t == "intent"
    assert event.id == "e1"
    assert event.at == "2026-06-05T12:30:00Z"
    assert event.by == "cli"

    # Check on-disk file
    log_path = tmp_path / ".capsule" / "log.jsonl"
    b = log_path.read_bytes()
    expected = event.to_jsonl().encode("utf-8") + b"\n"
    assert b == expected


def test_init_idempotent(tmp_path: Path) -> None:
    # 3. `init` idempotent.
    engine = Engine(tmp_path)
    engine.init()
    engine.record_intent(objective="Obj 1", constraints=[], acceptance=[])

    proj1 = engine.load()
    assert proj1.event_count == 1

    proj2 = engine.init()
    assert proj2.event_count == 1

    # Ensure we didn't truncate the log
    proj3 = engine.load()
    assert proj3.event_count == 1


def test_no_evidence_event_omits_verified(tmp_path: Path) -> None:
    # 10. No-evidence event omits `verified`.
    engine = Engine(tmp_path)
    engine.init()

    event = engine.record_decision(decision="D", rationale="R", evidence=[])
    assert event.evidence == ()
    assert event.verified is None

    line = event.to_jsonl()
    obj = json.loads(line)
    assert "evidence" not in obj
    assert "verified" not in obj


def test_dangling_closes_validation(tmp_path: Path) -> None:
    # 18. Dangling `closes`.
    engine = Engine(tmp_path)
    engine.init()

    with pytest.raises(SchemaError):
        engine.resolve_question("q_missing", "answer")


def test_already_resolved_question_validation(tmp_path: Path) -> None:
    # 19. Already-resolved question.
    engine = Engine(tmp_path)
    engine.init()

    engine.note_question("Q1", by="cli")
    engine.resolve_question(engine.log()[0].id, "A1")

    with pytest.raises(SchemaError):
        engine.resolve_question(engine.log()[0].id, "A2")


def _append_worker(repo: Path, count: int) -> None:
    engine = Engine(repo)
    for i in range(count):
        engine.record_intent(objective=f"Obj {i}", constraints=[], acceptance=[])


def test_n_process_append_stress(tmp_path: Path) -> None:
    # 25. N-process append stress.
    engine = Engine(tmp_path)
    engine.init()

    N = 8
    M = 10

    processes = []
    for _ in range(N):
        p = multiprocessing.Process(target=_append_worker, args=(tmp_path, M))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    proj = engine.load()
    assert proj.event_count == N * M
    events = engine.log()
    assert len(events) == N * M
    # Check all lines parseable (no CorruptLogLine)
    # Check all ids are present and unique
    ids = {e.id for e in events}
    assert len(ids) == N * M


def test_no_capsule(tmp_path: Path) -> None:
    # 23. No capsule.
    engine = Engine(tmp_path)
    with pytest.raises(NoCapsule, match="run `capsule init`"):
        engine.load()
    with pytest.raises(NoCapsule, match="run `capsule init`"):
        engine.log()
    with pytest.raises(NoCapsule, match="run `capsule init`"):
        engine.render()
    with pytest.raises(NoCapsule, match="run `capsule init`"):
        engine.record_intent("obj", [], [])


def test_not_implemented_stubs(tmp_path: Path) -> None:
    # 24. NotImplemented stubs
    engine = Engine(tmp_path)
    with pytest.raises(NotImplementedError):
        engine.diff("rev")
    with pytest.raises(NotImplementedError):
        engine.revert("rev")


def test_rejects_lock_symlink_escape_before_acquire(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    capsule_dir = repo / ".capsule"
    capsule_dir.mkdir()
    (capsule_dir / "log.jsonl").write_text("", encoding="utf-8")
    lock_link = capsule_dir / ".lock"
    try:
        lock_link.symlink_to(outside / ".lock")
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    engine = Engine(repo)
    with pytest.raises(CapsuleError, match="resolves outside repo root"):
        engine.record_intent("obj", constraints=[], acceptance=[])


def test_record_event_redacts_authored_text_but_not_evidence_refs(tmp_path: Path) -> None:
    engine = Engine(tmp_path)
    engine.init()
    commit_ref = "a" * 40

    event = engine.record_decision(
        decision="Use local mode",
        rationale="token sk-ABCD1234EFGH5678IJKL and A2345678901234567890123456789012",
        evidence=[Evidence("commit", commit_ref)],
    )

    assert event.rationale == "token [REDACTED] and [REDACTED]"
    assert event.evidence[0].ref == commit_ref

    log_text = (tmp_path / ".capsule" / "log.jsonl").read_text(encoding="utf-8")
    assert "sk-ABCD1234EFGH5678IJKL" not in log_text
    assert "A2345678901234567890123456789012" not in log_text
    assert "[REDACTED]" in log_text
    assert commit_ref in log_text
