"""capsule load."""

from __future__ import annotations

import argparse

from capsule.cli.commands import repo_from_args
from capsule.cli.formatting import Payload, render_capsule_body
from capsule.engine import Engine, Projection
from capsule.engine.events import ByValue, by_to_jsonable

NAME = "load"
HELP = "Load the folded capsule projection."


def configure(_parser: argparse.ArgumentParser) -> None:
    return None


def run(args: argparse.Namespace) -> Payload:
    engine = Engine(repo_from_args(args))
    projection = engine.load()
    events = engine.log()
    return {
        "_text": render_capsule_body(projection, events),
        "_json": _projection_payload(projection),
    }


def _projection_payload(projection: Projection) -> Payload:
    return {
        "objective": projection.objective,
        "current_understanding": list(projection.current_understanding),
        "constraints": list(projection.constraints),
        "invariants": list(projection.invariants),
        "acceptance": list(projection.acceptance),
        "decisions": [
            {
                "id": item.id,
                "at": item.at,
                "by": _json_by(item.by),
                "decision": item.decision,
                "rationale": item.rationale,
                "evidence": [{"kind": ev.kind, "ref": ev.ref} for ev in item.evidence],
                "verified": item.verified,
            }
            for item in projection.decisions
        ],
        "open_questions": [
            {
                "id": item.id,
                "at": item.at,
                "by": _json_by(item.by),
                "q": item.q,
            }
            for item in projection.open_questions
        ],
        "open_tasks": [
            {
                "task_id": item.task_id,
                "objective": item.objective,
                "started_at": item.started_at,
                "started_by": _json_by(item.started_by),
                "for_intent": item.for_intent,
            }
            for item in projection.open_tasks
        ],
        "resolved_questions": [
            {
                "id": item.id,
                "at": item.at,
                "by": _json_by(item.by),
                "q": item.q,
                "answer": item.answer,
                "resolved_by": item.resolved_by,
            }
            for item in projection.resolved_questions
        ],
        "progress": [
            {
                "id": item.id,
                "at": item.at,
                "by": _json_by(item.by),
                "note": item.note,
                "evidence": [{"kind": ev.kind, "ref": ev.ref} for ev in item.evidence],
                "verified": item.verified,
            }
            for item in projection.progress
        ],
        "event_count": projection.event_count,
    }


def _json_by(by: ByValue | None) -> object:
    if by is None:
        return None
    return by_to_jsonable(by)
