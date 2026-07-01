"""Deterministic fold from events to a projection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from capsule.engine.events import ByValue, Event, Evidence


@dataclass(frozen=True)
class DecisionView:
    id: str
    at: str
    by: ByValue | None
    decision: str
    rationale: str
    evidence: tuple[Evidence, ...]
    verified: bool | None


@dataclass(frozen=True)
class QuestionView:
    id: str
    at: str
    by: ByValue | None
    q: str
    answer: str | None = None
    resolved_by: str | None = None


@dataclass(frozen=True)
class ProgressView:
    id: str
    at: str
    by: ByValue | None
    note: str
    evidence: tuple[Evidence, ...]
    verified: bool | None


@dataclass(frozen=True)
class OpenTaskView:
    task_id: str
    objective: str
    started_at: str
    started_by: ByValue | None
    for_intent: str | None


@dataclass(frozen=True)
class Projection:
    objective: str | None
    current_understanding: tuple[str, ...]
    constraints: tuple[str, ...]
    invariants: tuple[str, ...]
    acceptance: tuple[str, ...]
    decisions: tuple[DecisionView, ...]
    open_questions: tuple[QuestionView, ...]
    resolved_questions: tuple[QuestionView, ...]
    progress: tuple[ProgressView, ...]
    event_count: int
    open_tasks: tuple[OpenTaskView, ...] = ()


def fold(events: tuple[Event, ...]) -> Projection:
    ordered = ordered_events(events)
    objective: str | None = None
    current_understanding: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    constraints: list[str] = []
    invariants: list[str] = []
    seen_constraints: set[str] = set()
    seen_invariants: set[str] = set()
    decisions: list[DecisionView] = []
    progress: list[ProgressView] = []
    questions: dict[str, QuestionView] = {}
    question_order: list[str] = []
    task_starts: dict[str, OpenTaskView] = {}

    for event in ordered:
        if event.t == "intent":
            objective = event.objective
            # Snapshot fields project *current* truth: the most recent intent that
            # supplies a non-empty value wins, so a refreshed understanding or a new
            # phase's acceptance replaces the prior one rather than piling up forever.
            # Omitting a field in a later intent leaves the prior snapshot intact.
            if event.current_understanding:
                current_understanding = event.current_understanding
            if event.acceptance:
                acceptance = event.acceptance
            # Cumulative fields union across intents: constraints and invariants are
            # standing rules that accrue over a project and are rarely retracted.
            _merge_unique(constraints, seen_constraints, event.constraints)
            _merge_unique(invariants, seen_invariants, event.invariants)
        elif event.t == "decision":
            decisions.append(
                DecisionView(
                    id=event.id,
                    at=event.at,
                    by=event.by,
                    decision=_require_value(event.decision),
                    rationale=_require_value(event.rationale),
                    evidence=event.evidence,
                    verified=event.verified,
                )
            )
        elif event.t == "question":
            questions[event.id] = QuestionView(
                id=event.id,
                at=event.at,
                by=event.by,
                q=_require_value(event.q),
            )
            question_order.append(event.id)
        elif event.t == "resolution":
            current = questions.get(_require_value(event.closes))
            if current is None or current.answer is not None:
                continue
            questions[current.id] = QuestionView(
                id=current.id,
                at=current.at,
                by=current.by,
                q=current.q,
                answer=_require_value(event.answer),
                resolved_by=event.id,
            )
        elif event.t == "progress":
            progress.append(
                ProgressView(
                    id=event.id,
                    at=event.at,
                    by=event.by,
                    note=_require_value(event.note),
                    evidence=event.evidence,
                    verified=event.verified,
                )
            )
        elif event.t == "task_start":
            task_id = _require_value(event.task_id)
            task_starts[task_id] = OpenTaskView(
                task_id=task_id,
                objective=_require_value(event.objective),
                started_at=event.at,
                started_by=event.by,
                for_intent=event.for_intent,
            )
        elif event.t == "task_end":
            task_starts.pop(_require_value(event.closes_task), None)

    open_questions: list[QuestionView] = []
    resolved_questions: list[QuestionView] = []
    for qid in question_order:
        question = questions[qid]
        if question.answer is None:
            open_questions.append(question)
        else:
            resolved_questions.append(question)
    open_tasks = tuple(sorted(task_starts.values(), key=lambda item: item.started_at))

    return Projection(
        objective=objective,
        current_understanding=current_understanding,
        constraints=tuple(constraints),
        invariants=tuple(invariants),
        acceptance=acceptance,
        decisions=tuple(decisions),
        open_questions=tuple(open_questions),
        resolved_questions=tuple(resolved_questions),
        progress=tuple(progress),
        event_count=len(events),
        open_tasks=open_tasks,
    )


def ordered_events(events: Sequence[Event]) -> tuple[Event, ...]:
    return tuple(event for _, event in sorted(enumerate(events), key=_order_key))


def _order_key(item: tuple[int, Event]) -> tuple[str, int]:
    index, event = item
    return event.at, index


def _merge_unique(target: list[str], seen: set[str], values: tuple[str, ...]) -> None:
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        target.append(value)


def _require_value(value: str | None) -> str:
    if value is None:
        raise ValueError("validated event field unexpectedly missing")
    return value
