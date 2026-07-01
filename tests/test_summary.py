import json
from pathlib import Path
from typing import Any

from capsule.cli.commands.context import PREAMBLE
from capsule.cli.formatting import render_capsule_body, render_projection_text
from capsule.cli.summary import (
    DECISIONS_LIMIT,
    PROGRESS_LIMIT,
    RESOLVED_QUESTIONS_LIMIT,
    open_work_lines,
    recent_activity_lines,
)
from capsule.engine.events import Event
from capsule.engine.fold import ProgressView, Projection, QuestionView, fold


def test_th1_objective_one_block_regression() -> None:
    """T-H1: Objective one-block regression."""
    projection = Projection(
        objective="This is a multi-word objective that should be rendered on a single line.",
        current_understanding=(),
        constraints=(),
        invariants=(),
        acceptance=(),
        decisions=(),
        open_questions=(),
        resolved_questions=(),
        progress=(),
        event_count=1,
    )
    text = render_projection_text(projection)
    # Check that it's rendered as one block, not character by character
    assert (
        "Objective:\n"
        "This is a multi-word objective that should be rendered on a single line.\n\n"
        "Current Understanding:"
    ) in text


def test_th2_composed_load_golden(invoke_main: Any, tmp_path: Path) -> None:
    """T-H2: Composed load golden."""
    capsule_dir = tmp_path / ".capsule"
    capsule_dir.mkdir()
    log_path = capsule_dir / "log.jsonl"

    events = [
        Event(
            t="intent", id="ev1", at="2024-01-01T00:00:00Z", by="alice", objective="Test objective"
        ),
        Event(t="question", id="ev2", at="2024-01-01T00:01:00Z", by="bob", q="Test question?"),
        Event(t="progress", id="ev3", at="2024-01-01T00:02:00Z", by="alice", note="Test progress"),
    ]
    with log_path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.to_jsonl() + "\n")

    res = invoke_main(["--repo", str(tmp_path), "load"])
    assert res.exit_code == 0
    text = res.stdout.replace("\r\n", "\n")

    # Asserts exact section ordering
    sections_in_order = [
        "Objective:\nTest objective",
        "Current Understanding:\n(none)",
        "Constraints:\n(none)",
        "Invariants:\n(none)",
        "Acceptance:\n(none)",
        "Decisions:\n(none)",
        "Open Questions:\n- (ev2) Test question?",
        "Open Tasks:\n(none)",
        "Resolved Questions:\n(none)",
        "Progress:\n- (ev3) Test progress\n  by: alice\n  at: 2024-01-01T00:02:00Z",
        "Open Work / Next Steps:\n- open question (ev2): Test question?\n"
        "- last progress (ev3): Test progress",
        "Event Count: 3",
        "Recent Activity:\n- (ev3) progress: Test progress  [by alice, at 2024-01-01T00:02:00Z]\n"
        "- (ev2) question: Test question?  [by bob, at 2024-01-01T00:01:00Z]\n"
        "- (ev1) intent: Test objective  [by alice, at 2024-01-01T00:00:00Z]",
    ]

    current_pos = 0
    for section in sections_in_order:
        pos = text.find(section, current_pos)
        assert pos != -1, f"Section not found in correct order: {section}"
        current_pos = pos + len(section)


def test_th3_composed_context_golden(invoke_main: Any, tmp_path: Path) -> None:
    """T-H3: Composed context golden."""
    capsule_dir = tmp_path / ".capsule"
    capsule_dir.mkdir()
    log_path = capsule_dir / "log.jsonl"

    events = [
        Event(t="intent", id="ev1", at="2024-01-01T00:00:00Z", by="alice", objective="Test obj"),
    ]
    with log_path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.to_jsonl() + "\n")

    # context --clip may fail in test env if clipboard is unavailable, but stdout/stderr is returned
    res = invoke_main(["--repo", str(tmp_path), "context"])
    assert res.exit_code == 0
    # Block is output either to stdout or stderr or retrieved via json
    res_json = invoke_main(["--repo", str(tmp_path), "--format", "json", "context"])
    assert res_json.exit_code == 0

    payload = json.loads(res_json.stdout)
    block = payload["block"]

    assert block.endswith("\n\n" + PREAMBLE)
    assert "Recent Activity:" in block
    assert "Test obj" in block


def test_th4_render_capsule_body_bounds_history_sections() -> None:
    events = _history_fixture_events(
        decisions=DECISIONS_LIMIT + 2,
        resolved_questions=RESOLVED_QUESTIONS_LIMIT + 2,
        progress=PROGRESS_LIMIT + 2,
    )
    projection = fold(tuple(events))

    text = render_capsule_body(projection, events)

    assert "Open Work / Next Steps:" in text
    assert "Recent Activity:" in text
    assert "- (oq1) Open question 1?" in text
    assert "- (oq2) Open question 2?" in text
    assert "(d1)" not in text
    assert "(d2)" not in text
    for index in range(3, DECISIONS_LIMIT + 3):
        assert f"(d{index})" in text
    assert (
        "... 2 earlier decisions omitted — run `capsule show` or `capsule log` for the full record"
        in text
    )
    assert "(rq1) Resolved question 1? -> Answer 1 (resolved_by rr1)" not in text
    assert "(rq2) Resolved question 2? -> Answer 2 (resolved_by rr2)" not in text
    for index in range(3, RESOLVED_QUESTIONS_LIMIT + 3):
        assert f"(rq{index}) Resolved question {index}? -> Answer {index}" in text
    assert (
        "... 2 earlier resolved questions omitted — run `capsule show` for the full record" in text
    )
    assert "(p1) Progress 1" not in text
    assert "(p2) Progress 2" not in text
    for index in range(3, PROGRESS_LIMIT + 3):
        assert f"(p{index}) Progress {index}" in text
    assert "... 2 earlier progress entries omitted — run `capsule show` for the full record" in text


def test_th5_render_capsule_body_matches_full_output_at_or_under_caps() -> None:
    cases = (
        (DECISIONS_LIMIT - 1, RESOLVED_QUESTIONS_LIMIT - 1, PROGRESS_LIMIT - 1),
        (DECISIONS_LIMIT, RESOLVED_QUESTIONS_LIMIT, PROGRESS_LIMIT),
    )
    for decisions, resolved_questions, progress in cases:
        events = _history_fixture_events(
            decisions=decisions,
            resolved_questions=resolved_questions,
            progress=progress,
        )
        projection = fold(tuple(events))

        text = render_capsule_body(projection, events)
        expected = (
            render_projection_text(projection)
            + "\n\nRecent Activity:\n"
            + "\n".join(recent_activity_lines(events))
        )

        assert text == expected
        assert "earlier decisions omitted" not in text
        assert "earlier resolved questions omitted" not in text
        assert "earlier progress entries omitted" not in text


# open_work_lines unit matrix
def test_to1_open_work_both_empty() -> None:
    """T-O1: both empty -> ['(none)']."""
    proj = Projection(
        objective=None,
        current_understanding=(),
        constraints=(),
        invariants=(),
        acceptance=(),
        decisions=(),
        open_questions=(),
        resolved_questions=(),
        progress=(),
        event_count=0,
    )
    assert open_work_lines(proj) == ["(none)"]


def test_to2_open_work_questions_only() -> None:
    """T-O2: questions only."""
    proj = Projection(
        objective=None,
        current_understanding=(),
        constraints=(),
        invariants=(),
        acceptance=(),
        decisions=(),
        open_questions=(
            QuestionView(id="q1", at="t", by="b", q="q1?"),
            QuestionView(id="q2", at="t", by="b", q="q2?"),
        ),
        resolved_questions=(),
        progress=(),
        event_count=2,
    )
    assert open_work_lines(proj) == [
        "- open question (q1): q1?",
        "- open question (q2): q2?",
    ]


def test_to3_open_work_progress_only() -> None:
    """T-O3: progress only."""
    proj = Projection(
        objective=None,
        current_understanding=(),
        constraints=(),
        invariants=(),
        acceptance=(),
        decisions=(),
        open_questions=(),
        resolved_questions=(),
        progress=(
            ProgressView(id="p1", at="t", by="b", note="note1", evidence=(), verified=None),
            ProgressView(id="p2", at="t", by="b", note="note2", evidence=(), verified=None),
        ),
        event_count=2,
    )
    assert open_work_lines(proj) == ["- last progress (p2): note2"]


def test_to4_open_work_both_present() -> None:
    """T-O4: both present."""
    proj = Projection(
        objective=None,
        current_understanding=(),
        constraints=(),
        invariants=(),
        acceptance=(),
        decisions=(),
        open_questions=(QuestionView(id="q1", at="t", by="b", q="q1?"),),
        resolved_questions=(),
        progress=(
            ProgressView(id="p1", at="t", by="b", note="note1", evidence=(), verified=None),
            ProgressView(id="p2", at="t", by="b", note="note2", evidence=(), verified=None),
        ),
        event_count=3,
    )
    assert open_work_lines(proj) == ["- open question (q1): q1?", "- last progress (p2): note2"]


# recent_activity_lines unit matrix
def test_tr1_recent_activity_empty_log() -> None:
    """T-R1: empty log -> ['(none)']."""
    assert recent_activity_lines([]) == ["(none)"]


def test_tr2_recent_activity_len_lt_k() -> None:
    """T-R2: len < K."""
    events = [
        Event(t="intent", id="e1", at="t1", by="b", objective="o1"),
        Event(t="intent", id="e2", at="t2", by="b", objective="o2"),
    ]
    lines = recent_activity_lines(events, limit=5)
    assert len(lines) == 2
    assert lines[0].startswith("- (e2)")
    assert lines[1].startswith("- (e1)")


def test_tr3_recent_activity_len_eq_k() -> None:
    """T-R3: len == K."""
    events = [
        Event(t="intent", id=f"e{i}", at=f"t{i}", by="b", objective=f"o{i}") for i in range(1, 4)
    ]
    lines = recent_activity_lines(events, limit=3)
    assert len(lines) == 3
    assert lines[0].startswith("- (e3)")
    assert lines[2].startswith("- (e1)")


def test_tr4_recent_activity_len_gt_k() -> None:
    """T-R4: len > K."""
    events = [
        Event(t="intent", id=f"e{i}", at=f"t{i}", by="b", objective=f"o{i}") for i in range(1, 6)
    ]
    lines = recent_activity_lines(events, limit=3)
    assert len(lines) == 3
    assert lines[0].startswith("- (e5)")
    assert lines[1].startswith("- (e4)")
    assert lines[2].startswith("- (e3)")


def test_tr5_recent_activity_per_type_summary() -> None:
    """T-R5: per-type summary mapping."""
    events = [
        Event(t="intent", id="e1", at="t", by="b", objective="obj"),
        Event(t="decision", id="e2", at="t", by="b", decision="dec"),
        Event(t="question", id="e3", at="t", by="b", q="que"),
        Event(t="resolution", id="e4", at="t", by="b", closes="e3", answer="ans"),
        Event(t="progress", id="e5", at="t", by="b", note="not"),
        Event(t="unknown", id="e6", at="t", by="b"),  # forward compat
    ]
    lines = recent_activity_lines(events, limit=6)
    assert lines[5] == "- (e1) intent: obj  [by b, at t]"
    assert lines[4] == "- (e2) decision: dec  [by b, at t]"
    assert lines[3] == "- (e3) question: que  [by b, at t]"
    assert lines[2] == "- (e4) resolution: closes e3: ans  [by b, at t]"
    assert lines[1] == "- (e5) progress: not  [by b, at t]"
    assert lines[0] == "- (e6) unknown:   [by b, at t]"


def test_tr6_recent_activity_by_none() -> None:
    """T-R6: by is None."""
    events = [Event(t="intent", id="e1", at="t", by=None, objective="obj")]
    lines = recent_activity_lines(events, limit=1)
    assert "  [by (none), at t]" in lines[0]


def test_tr7_recent_activity_length_cap() -> None:
    """T-R7: length cap and multiline collapse."""
    long_obj = "A" * 150
    multiline_obj = "Line 1\n\nLine 2\t\tLine 3"
    events = [
        Event(t="intent", id="e1", at="t", by="b", objective=long_obj),
        Event(t="intent", id="e2", at="t", by="b", objective=multiline_obj),
    ]
    lines = recent_activity_lines(events, limit=2)
    # e2 is newer, so it's first
    assert "Line 1 Line 2 Line 3" in lines[0]

    # e1 is second
    # "A"*97 + "..." = 100 chars
    summary_part = lines[1].split("intent: ")[1].split("  [by")[0]
    assert len(summary_part) == 100
    assert summary_part.endswith("...")
    assert summary_part.startswith("A" * 97)


def _history_fixture_events(
    *, decisions: int, resolved_questions: int, progress: int
) -> list[Event]:
    events = [
        Event(
            t="intent",
            id="intent1",
            at=_at(0),
            by="alice",
            objective="Ship bounded load/context text",
            current_understanding=("CLI summary layer only; render.py remains full.",),
            constraints=("Keep frozen JSON payloads unchanged.",),
            invariants=("In-repo capsule storage under `.capsule/`.",),
            acceptance=("Bound only the shared text body.",),
        ),
        Event(t="question", id="oq1", at=_at(1), by="alice", q="Open question 1?"),
        Event(t="question", id="oq2", at=_at(2), by="alice", q="Open question 2?"),
    ]
    index = 3
    for item in range(1, decisions + 1):
        events.append(
            Event(
                t="decision",
                id=f"d{item}",
                at=_at(index),
                by="alice",
                decision=f"Decision {item}",
                rationale=f"Rationale {item}",
            )
        )
        index += 1
    for item in range(1, resolved_questions + 1):
        events.append(
            Event(
                t="question",
                id=f"rq{item}",
                at=_at(index),
                by="bob",
                q=f"Resolved question {item}?",
            )
        )
        index += 1
        events.append(
            Event(
                t="resolution",
                id=f"rr{item}",
                at=_at(index),
                by="bob",
                closes=f"rq{item}",
                answer=f"Answer {item}",
            )
        )
        index += 1
    for item in range(1, progress + 1):
        events.append(
            Event(
                t="progress",
                id=f"p{item}",
                at=_at(index),
                by="alice",
                note=f"Progress {item}",
            )
        )
        index += 1
    return events


def _at(index: int) -> str:
    return f"2024-01-01T00:{index:02d}:00Z"
