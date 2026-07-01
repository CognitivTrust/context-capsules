"""capsule record."""

from __future__ import annotations

import argparse
import json

from capsule.cli.commands import add_by_arguments, repo_from_args, resolve_by
from capsule.cli.edge import parse_evidence
from capsule.cli.formatting import Payload
from capsule.engine import Engine, Event

NAME = "record"
HELP = "Append a typed capsule event."


def configure(parser: argparse.ArgumentParser) -> None:
    kind_parent = argparse.ArgumentParser(add_help=False)
    add_by_arguments(kind_parent, default="cli")

    kinds = parser.add_subparsers(dest="kind", required=True)

    intent = kinds.add_parser("intent", parents=[kind_parent])
    intent.add_argument("--objective", required=True)
    intent.add_argument("--current-understanding", action="append", default=[])
    intent.add_argument("--constraint", action="append", default=[])
    intent.add_argument("--invariant", action="append", default=[])
    intent.add_argument("--acceptance", action="append", default=[])

    decision = kinds.add_parser("decision", parents=[kind_parent])
    decision.add_argument("--decision", required=True)
    decision.add_argument("--rationale", required=True)
    decision.add_argument("--evidence", action="append", default=[], type=parse_evidence)

    question = kinds.add_parser("question", parents=[kind_parent])
    question.add_argument("--question", "-q", required=True)

    resolution = kinds.add_parser("resolution", parents=[kind_parent])
    resolution.add_argument("--closes", required=True)
    resolution.add_argument("--answer", required=True)

    progress = kinds.add_parser("progress", parents=[kind_parent])
    progress.add_argument("--note", required=True)
    progress.add_argument("--evidence", action="append", default=[], type=parse_evidence)


def run(args: argparse.Namespace) -> Payload:
    engine = Engine(repo_from_args(args))
    event = _record(engine, args)
    event_json = json.loads(event.to_jsonl())
    return {
        "_text": _record_text(event),
        "_json": event_json,
    }


def _record(engine: Engine, args: argparse.Namespace) -> Event:
    by = resolve_by(args)
    if args.kind == "intent":
        return engine.record_intent(
            args.objective,
            constraints=list(args.constraint),
            acceptance=list(args.acceptance),
            by=by,
            current_understanding=list(args.current_understanding),
            invariants=list(args.invariant),
        )
    if args.kind == "decision":
        return engine.record_decision(
            args.decision,
            args.rationale,
            evidence=list(args.evidence),
            by=by,
        )
    if args.kind == "question":
        return engine.note_question(args.question, by=by)
    if args.kind == "resolution":
        return engine.resolve_question(args.closes, args.answer, by=by)
    return engine.mark_progress(
        args.note,
        evidence=list(args.evidence),
        by=by,
    )


def _record_text(event: Event) -> str:
    suffix = ""
    if event.verified is not None:
        suffix = f" verified={json.dumps(event.verified)}"
    return f"Recorded {event.t} {event.id}.{suffix}"
