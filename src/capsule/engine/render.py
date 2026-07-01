"""Deterministic markdown rendering for a projection."""

from __future__ import annotations

from capsule.engine.events import Evidence, format_by
from capsule.engine.fold import DecisionView, OpenTaskView, ProgressView, Projection, QuestionView


def render(projection: Projection) -> str:
    sections = [
        ("Objective", projection.objective or "_None yet._"),
        ("Current Understanding", _render_bullets(projection.current_understanding)),
        ("Constraints", _render_bullets(projection.constraints)),
        ("Invariants", _render_bullets(projection.invariants)),
        ("Acceptance", _render_bullets(projection.acceptance)),
        ("Decisions", _render_decisions(projection.decisions)),
        ("Open Questions", _render_open_questions(projection.open_questions)),
        ("Open Tasks", _render_open_tasks(projection.open_tasks)),
        ("Resolved Questions", _render_resolved_questions(projection.resolved_questions)),
        ("Progress", _render_progress(projection.progress)),
    ]
    lines = ["# Capsule", ""]
    for index, (title, body) in enumerate(sections):
        lines.append(f"## {title}")
        lines.extend(body.split("\n"))
        if index != len(sections) - 1:
            lines.append("")
    return "\n".join(lines) + "\n"


def _render_bullets(items: tuple[str, ...]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _render_decisions(items: tuple[DecisionView, ...]) -> str:
    if not items:
        return "_None._"
    lines: list[str] = []
    for index, item in enumerate(items):
        if index:
            lines.append("")
        lines.append(f"- {item.decision}")
        lines.append(f"  - rationale: {item.rationale}")
        if item.evidence:
            lines.append(
                "  - evidence: "
                f"{_render_evidence(item.evidence)} (verified: {_bool_text(item.verified)})"
            )
    return "\n".join(lines)


def _render_open_questions(items: tuple[QuestionView, ...]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- ({item.id}) {item.q}" for item in items)


def _render_resolved_questions(items: tuple[QuestionView, ...]) -> str:
    if not items:
        return "_None._"
    return "\n".join(
        f"- ({item.id}) {item.q} -> {item.answer} (resolved_by {item.resolved_by})"
        for item in items
    )


def _render_open_tasks(items: tuple[OpenTaskView, ...]) -> str:
    if not items:
        return "_None._"
    lines: list[str] = []
    for index, item in enumerate(items):
        if index:
            lines.append("")
        lines.append(
            f"- ({item.task_id}) {item.objective} "
            f"[by {format_by(item.started_by)}, at {item.started_at}]"
        )
        if item.for_intent is not None:
            lines.append(f"  - for_intent: {item.for_intent}")
    return "\n".join(lines)


def _render_progress(items: tuple[ProgressView, ...]) -> str:
    if not items:
        return "_None._"
    lines: list[str] = []
    for index, item in enumerate(items):
        if index:
            lines.append("")
        lines.append(f"- {item.note}")
        if item.evidence:
            lines.append(
                "  - evidence: "
                f"{_render_evidence(item.evidence)} (verified: {_bool_text(item.verified)})"
            )
    return "\n".join(lines)


def _render_evidence(items: tuple[Evidence, ...]) -> str:
    return ", ".join(f"{item.kind}:{item.ref}" for item in items)


def _bool_text(value: bool | None) -> str:
    return "true" if value else "false"
