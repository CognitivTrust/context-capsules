"""capsule task."""

from __future__ import annotations

import argparse
import json

from capsule.cli.commands import add_by_arguments, repo_from_args, resolve_by
from capsule.cli.formatting import Payload
from capsule.engine import Engine, Event

NAME = "task"
HELP = "Append task lifecycle events."


def configure(parser: argparse.ArgumentParser) -> None:
    subcommands = parser.add_subparsers(dest="task_command", required=True)

    start = subcommands.add_parser("start")
    start.add_argument("--task-id", required=True)
    start.add_argument("--objective", required=True)
    start.add_argument("--for-intent", default=None)
    add_by_arguments(start, default="cli")

    end = subcommands.add_parser("end")
    end.add_argument("--task-id", required=True)
    end.add_argument("--outcome", required=True)
    end.add_argument("--summary", default=None)
    add_by_arguments(end, default="cli")


def run(args: argparse.Namespace) -> Payload:
    engine = Engine(repo_from_args(args))
    event = _record_task(engine, args)
    event_json = json.loads(event.to_jsonl())
    return {
        "_text": _task_text(event),
        "_json": event_json,
    }


def _record_task(engine: Engine, args: argparse.Namespace) -> Event:
    by = resolve_by(args)
    if args.task_command == "start":
        return engine.start_task(
            args.task_id,
            args.objective,
            by=by,
            for_intent=args.for_intent,
        )
    return engine.end_task(
        args.task_id,
        args.outcome,
        by=by,
        summary=args.summary,
    )


def _task_text(event: Event) -> str:
    return f"Recorded {event.t} {event.id}."
