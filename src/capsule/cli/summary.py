"""Read-only CLI summary helpers for projection and log-derived text."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from capsule.engine import Event, Projection
from capsule.engine.events import format_by

DECISIONS_LIMIT: int = 8
PROGRESS_LIMIT: int = 5
OPEN_TASKS_LIMIT: int = 5
RESOLVED_QUESTIONS_LIMIT: int = 5
RECENT_ACTIVITY_DEFAULT: int = 5
_EMPTY = "(none)"
_SUMMARY_MAX = 100
_T = TypeVar("_T")


@dataclass(frozen=True)
class BoundedItems(Generic[_T]):
    items: tuple[_T, ...]
    omitted_count: int


def open_work_lines(projection: Projection) -> list[str]:
    lines = [f"- open question ({item.id}): {item.q}" for item in projection.open_questions]
    if projection.progress:
        latest = projection.progress[-1]
        lines.append(f"- last progress ({latest.id}): {latest.note}")
    if not lines:
        return [_EMPTY]
    return lines


def recent_activity_lines(
    events: Sequence[Event], *, limit: int = RECENT_ACTIVITY_DEFAULT
) -> list[str]:
    if not events:
        return [_EMPTY]
    lines: list[str] = []
    for event in reversed(events[-limit:]):
        by = format_by(event.by)
        summary = _event_summary(event)
        lines.append(f"- ({event.id}) {event.t}: {summary}  [by {by}, at {event.at}]")
    return lines


def _event_summary(event: Event) -> str:
    if event.t == "intent":
        value = event.objective or ""
    elif event.t == "decision":
        value = event.decision or ""
    elif event.t == "question":
        value = event.q or ""
    elif event.t == "resolution":
        value = f"closes {event.closes or ''}: {event.answer or ''}"
    elif event.t == "progress":
        value = event.note or ""
    elif event.t == "task_start":
        value = f"{event.task_id or ''}: {event.objective or ''}"
    elif event.t == "task_end":
        value = f"{event.closes_task or ''}: {event.outcome or ''} {event.summary or ''}".strip()
    else:
        value = ""
    return _summarize(value)


def _summarize(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > _SUMMARY_MAX:
        return collapsed[: _SUMMARY_MAX - 3] + "..."
    return collapsed


def bounded_recent_items(items: Sequence[_T], *, limit: int) -> BoundedItems[_T]:
    omitted_count = len(items) - limit
    if omitted_count <= 0:
        return BoundedItems(tuple(items), 0)
    return BoundedItems(tuple(items[-limit:]), omitted_count)


def omitted_history_line(
    omitted_count: int, *, singular: str, plural: str, hint: str
) -> str | None:
    if omitted_count <= 0:
        return None
    noun = singular if omitted_count == 1 else plural
    return f"... {omitted_count} earlier {noun} omitted — {hint}"
