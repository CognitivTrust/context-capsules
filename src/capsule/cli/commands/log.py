"""capsule log."""

from __future__ import annotations

import argparse
import json

from capsule.cli.commands import repo_from_args
from capsule.cli.formatting import Payload
from capsule.engine import Engine, Event
from capsule.engine.events import format_by

NAME = "log"
HELP = "Show capsule event history."


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=_non_negative_int, default=None)


def run(args: argparse.Namespace) -> Payload:
    events = Engine(repo_from_args(args)).log()
    selected = _select_events(events, args.limit)
    event_json = [json.loads(event.to_jsonl()) for event in selected]
    return {
        "_text": "\n".join(_render_line(event) for event in selected),
        "_json": event_json,
    }


def _select_events(events: list[Event], limit: int | None) -> list[Event]:
    if limit is None:
        return events
    if limit == 0:
        return []
    return events[-limit:]


def _render_line(event: Event) -> str:
    by = format_by(event.by) if event.by is not None else ""
    parts = [event.at, event.t, by, _summary(event)]
    line = "  ".join(parts)
    if event.verified is not None:
        line += f"  verified={json.dumps(event.verified)}"
    return line


def _summary(event: Event) -> str:
    if event.t == "intent":
        return _single_line(event.objective)
    if event.t == "decision":
        return _single_line(event.decision)
    if event.t == "question":
        return _single_line(event.q)
    if event.t == "resolution":
        return f"{event.closes} -> {_single_line(event.answer)}"
    if event.t == "task_start":
        return f"{event.task_id} -> {_single_line(event.objective)}"
    if event.t == "task_end":
        summary = _single_line(event.summary)
        prefix = f"{event.closes_task} -> {event.outcome}"
        return prefix if summary == "" else f"{prefix}: {summary}"
    return _single_line(event.note)


def _single_line(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("limit must be non-negative")
    return parsed
