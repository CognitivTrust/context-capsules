import json
from pathlib import Path

from capsule.engine.events import Event, Evidence
from capsule.engine.fold import fold
from capsule.engine.schema import from_obj


def _load_events(path: Path) -> tuple[Event, ...]:
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    return tuple(from_obj(json.loads(line)) for line in lines)


def test_canonical_fold() -> None:
    # 4. `load` folds canonical fixture.
    canonical_path = Path(__file__).parent / "fixtures" / "canonical.jsonl"
    events = _load_events(canonical_path)
    proj = fold(events)

    assert proj.objective == "Add Google OAuth"
    assert proj.current_understanding == ("auth uses JWT sessions",)
    assert proj.constraints == ("email/password login must keep working",)
    assert proj.invariants == ("session model unchanged",)
    assert proj.acceptance == ("user can sign in with Google",)

    assert len(proj.decisions) == 1
    d = proj.decisions[0]
    assert d.id == "e2"
    assert d.decision == "Use OAuth2 authorization-code flow"
    assert d.evidence[0] == Evidence("file", "auth/google.py")

    assert len(proj.open_questions) == 0
    assert len(proj.resolved_questions) == 1
    rq = proj.resolved_questions[0]
    assert rq.id == "q1"
    assert rq.resolved_by == "r1"
    assert rq.answer == "No — defer."

    assert len(proj.progress) == 1
    assert proj.progress[0].id == "e3"

    assert proj.open_tasks == ()
    assert proj.event_count == 7


def test_multi_intent_union() -> None:
    # 7. Multi-intent union.
    e1 = Event(
        t="intent",
        id="1",
        at="2026-06-05T10:00:00Z",
        by="cli",
        objective="Obj 1",
        constraints=("C1", "C2"),
    )
    e2 = Event(
        t="intent",
        id="2",
        at="2026-06-05T11:00:00Z",
        by="cli",
        objective="Obj 2",
        constraints=("C2", "C3"),
    )
    proj = fold((e1, e2))
    # objective = most recent intent's
    assert proj.objective == "Obj 2"
    # first-seen-order dedup union
    assert proj.constraints == ("C1", "C2", "C3")


def test_snapshot_fields_take_latest_intent() -> None:
    # current_understanding and acceptance are snapshots: the latest intent that
    # supplies them replaces the prior value rather than accumulating it.
    e1 = Event(
        t="intent",
        id="1",
        at="2026-06-05T10:00:00Z",
        by="cli",
        objective="Obj 1",
        current_understanding=("greenfield, nothing built yet",),
        acceptance=("phase 1: scaffolding exists",),
        invariants=("INV1",),
    )
    e2 = Event(
        t="intent",
        id="2",
        at="2026-06-05T11:00:00Z",
        by="cli",
        objective="Obj 2",
        current_understanding=("engine + CLI implemented; tests passing",),
        acceptance=("phase 2: load folds the log",),
        invariants=("INV2",),
    )
    proj = fold((e1, e2))
    # Stale "greenfield" understanding and phase-1 acceptance do not survive.
    assert proj.current_understanding == ("engine + CLI implemented; tests passing",)
    assert proj.acceptance == ("phase 2: load folds the log",)
    # Invariants still union across intents (standing rules accrue).
    assert proj.invariants == ("INV1", "INV2")


def test_snapshot_fields_preserved_when_later_intent_omits_them() -> None:
    # A later intent that updates the objective but omits the snapshot fields
    # leaves the prior snapshot intact instead of clearing it.
    e1 = Event(
        t="intent",
        id="1",
        at="2026-06-05T10:00:00Z",
        by="cli",
        objective="Obj 1",
        current_understanding=("auth uses JWT sessions",),
        acceptance=("user can sign in with Google",),
    )
    e2 = Event(
        t="intent",
        id="2",
        at="2026-06-05T11:00:00Z",
        by="cli",
        objective="Obj 2",
    )
    proj = fold((e1, e2))
    assert proj.objective == "Obj 2"
    assert proj.current_understanding == ("auth uses JWT sessions",)
    assert proj.acceptance == ("user can sign in with Google",)


def test_ordering_tiebreak() -> None:
    # 8. Ordering tiebreak. Same at, keeps insertion order.
    # To observe this, we add two progress events with the exact same at.
    p1 = Event(t="progress", id="1", at="2026-06-05T10:00:00Z", by="cli", note="A")
    p2 = Event(t="progress", id="2", at="2026-06-05T10:00:00Z", by="cli", note="B")

    proj1 = fold((p1, p2))
    assert proj1.progress[0].id == "1"
    assert proj1.progress[1].id == "2"

    proj2 = fold((p2, p1))
    assert proj2.progress[0].id == "2"
    assert proj2.progress[1].id == "1"


def test_open_vs_resolved_questions() -> None:
    # 9. Open vs resolved questions.
    q1 = Event(t="question", id="q1", at="2026-06-05T10:00:00Z", by="cli", q="Q1")
    q2 = Event(t="question", id="q2", at="2026-06-05T11:00:00Z", by="cli", q="Q2")
    r1 = Event(
        t="resolution", id="r1", at="2026-06-05T12:00:00Z", by="cli", closes="q1", answer="A1"
    )

    proj = fold((q1, q2, r1))

    assert len(proj.open_questions) == 1
    assert proj.open_questions[0].id == "q2"

    assert len(proj.resolved_questions) == 1
    assert proj.resolved_questions[0].id == "q1"
    assert proj.resolved_questions[0].answer == "A1"
    assert proj.resolved_questions[0].resolved_by == "r1"


def test_dangling_resolution_ignored() -> None:
    # A resolution whose closes matches no question is ignored by fold
    r1 = Event(
        t="resolution",
        id="r1",
        at="2026-06-05T12:00:00Z",
        by="cli",
        closes="q_missing",
        answer="A1",
    )
    proj = fold((r1,))
    assert len(proj.open_questions) == 0
    assert len(proj.resolved_questions) == 0
