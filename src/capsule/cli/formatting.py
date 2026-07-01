"""Output rendering seam: commands return payloads, the shell renders them."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from capsule.cli.summary import (
    DECISIONS_LIMIT,
    OPEN_TASKS_LIMIT,
    PROGRESS_LIMIT,
    RESOLVED_QUESTIONS_LIMIT,
    bounded_recent_items,
    omitted_history_line,
    open_work_lines,
    recent_activity_lines,
)
from capsule.engine import (
    DecisionView,
    Event,
    Evidence,
    OpenTaskView,
    ProgressView,
    Projection,
    QuestionView,
)
from capsule.engine.events import ByValue, format_by

Payload = dict[str, object]
_EMPTY = "(none)"


def format_output(payload: object, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if fmt == "text":
        if isinstance(payload, Mapping):
            if "message" in payload:
                return str(payload["message"])
            return "\n".join(f"{key}: {payload[key]}" for key in sorted(payload))
        return str(payload)
    raise ValueError(f"unknown format: {fmt!r}")


def render_projection_text(projection: Projection) -> str:
    sections = [
        ("Objective", [projection.objective] if projection.objective else [_EMPTY]),
        ("Current Understanding", _render_list(projection.current_understanding)),
        ("Constraints", _render_list(projection.constraints)),
        ("Invariants", _render_list(projection.invariants)),
        ("Acceptance", _render_list(projection.acceptance)),
        ("Decisions", _render_decisions(projection.decisions)),
        ("Open Questions", _render_open_questions(projection.open_questions)),
        ("Open Tasks", _render_open_tasks(projection.open_tasks)),
        ("Resolved Questions", _render_resolved_questions(projection.resolved_questions)),
        ("Progress", _render_progress(projection.progress)),
        ("Open Work / Next Steps", open_work_lines(projection)),
    ]
    lines: list[str] = []
    for index, (title, body_lines) in enumerate(sections):
        lines.append(f"{title}:")
        lines.extend(body_lines)
        if index != len(sections) - 1:
            lines.append("")
    lines.append("")
    lines.append(f"Event Count: {projection.event_count}")
    return "\n".join(lines)


def render_capsule_body(projection: Projection, events: Sequence[Event]) -> str:
    """Projection text plus the newest-first Recent Activity footer (load/context shared body)."""
    return (
        _render_bounded_projection_text(projection)
        + "\n\nRecent Activity:\n"
        + "\n".join(recent_activity_lines(events))
    )


def _render_list(items: Sequence[str]) -> list[str]:
    if not items:
        return [_EMPTY]
    return [f"- {item}" for item in items]


def _render_decisions(items: Sequence[DecisionView]) -> list[str]:
    if not items:
        return [_EMPTY]
    lines: list[str] = []
    for item in items:
        lines.append(f"- ({item.id}) {item.decision}")
        lines.append(f"  rationale: {item.rationale}")
        lines.append(f"  by: {_render_by(item.by)}")
        lines.append(f"  at: {item.at}")
        lines.extend(_evidence_lines(item.evidence, item.verified))
    return lines


def _render_open_questions(items: Sequence[QuestionView]) -> list[str]:
    if not items:
        return [_EMPTY]
    return [f"- ({item.id}) {item.q}" for item in items]


def _render_resolved_questions(items: Sequence[QuestionView]) -> list[str]:
    if not items:
        return [_EMPTY]
    return [
        f"- ({item.id}) {item.q} -> {item.answer} (resolved_by {item.resolved_by})"
        for item in items
    ]


def _render_open_tasks(items: Sequence[OpenTaskView]) -> list[str]:
    if not items:
        return [_EMPTY]
    lines: list[str] = []
    for item in items:
        lines.append(f"- ({item.task_id}) {item.objective}")
        lines.append(f"  by: {_render_by(item.started_by)}")
        lines.append(f"  at: {item.started_at}")
        lines.append(f"  for_intent: {item.for_intent or _EMPTY}")
    return lines


def _render_progress(items: Sequence[ProgressView]) -> list[str]:
    if not items:
        return [_EMPTY]
    lines: list[str] = []
    for item in items:
        lines.append(f"- ({item.id}) {item.note}")
        lines.append(f"  by: {_render_by(item.by)}")
        lines.append(f"  at: {item.at}")
        lines.extend(_evidence_lines(item.evidence, item.verified))
    return lines


def _evidence_lines(evidence: Sequence[Evidence], verified: bool | None) -> list[str]:
    lines: list[str] = []
    if evidence:
        lines.append("  evidence: " + ", ".join(f"{item.kind}:{item.ref}" for item in evidence))
    if verified is not None:
        lines.append(f"  verified: {_bool_text(verified)}")
    return lines


def _render_bounded_projection_text(projection: Projection) -> str:
    sections = [
        ("Objective", [projection.objective] if projection.objective else [_EMPTY]),
        ("Current Understanding", _render_list(projection.current_understanding)),
        ("Constraints", _render_list(projection.constraints)),
        ("Invariants", _render_list(projection.invariants)),
        ("Acceptance", _render_list(projection.acceptance)),
        ("Decisions", _render_bounded_decisions(projection.decisions)),
        ("Open Questions", _render_open_questions(projection.open_questions)),
        ("Open Tasks", _render_bounded_open_tasks(projection.open_tasks)),
        ("Resolved Questions", _render_bounded_resolved_questions(projection.resolved_questions)),
        ("Progress", _render_bounded_progress(projection.progress)),
        ("Open Work / Next Steps", open_work_lines(projection)),
    ]
    lines: list[str] = []
    for index, (title, body_lines) in enumerate(sections):
        lines.append(f"{title}:")
        lines.extend(body_lines)
        if index != len(sections) - 1:
            lines.append("")
    lines.append("")
    lines.append(f"Event Count: {projection.event_count}")
    return "\n".join(lines)


def _render_bounded_decisions(items: Sequence[DecisionView]) -> list[str]:
    bounded = bounded_recent_items(items, limit=DECISIONS_LIMIT)
    lines = _render_decisions(bounded.items)
    return _append_trailer(
        lines,
        omitted_history_line(
            bounded.omitted_count,
            singular="decision",
            plural="decisions",
            hint="run `capsule show` or `capsule log` for the full record",
        ),
    )


def _render_bounded_resolved_questions(items: Sequence[QuestionView]) -> list[str]:
    bounded = bounded_recent_items(items, limit=RESOLVED_QUESTIONS_LIMIT)
    lines = _render_resolved_questions(bounded.items)
    return _append_trailer(
        lines,
        omitted_history_line(
            bounded.omitted_count,
            singular="resolved question",
            plural="resolved questions",
            hint="run `capsule show` for the full record",
        ),
    )


def _render_bounded_progress(items: Sequence[ProgressView]) -> list[str]:
    bounded = bounded_recent_items(items, limit=PROGRESS_LIMIT)
    lines = _render_progress(bounded.items)
    return _append_trailer(
        lines,
        omitted_history_line(
            bounded.omitted_count,
            singular="progress entry",
            plural="progress entries",
            hint="run `capsule show` for the full record",
        ),
    )


def _render_bounded_open_tasks(items: Sequence[OpenTaskView]) -> list[str]:
    bounded = bounded_recent_items(items, limit=OPEN_TASKS_LIMIT)
    lines = _render_open_tasks(bounded.items)
    return _append_trailer(
        lines,
        omitted_history_line(
            bounded.omitted_count,
            singular="open task",
            plural="open tasks",
            hint="run `capsule show` for the full record",
        ),
    )


def _append_trailer(lines: list[str], trailer: str | None) -> list[str]:
    if trailer is None:
        return lines
    return [*lines, trailer]


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _render_by(by: ByValue | None) -> str:
    if by is None:
        return _EMPTY
    return format_by(by)
