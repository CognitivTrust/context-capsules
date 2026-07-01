"""capsule apply."""

from __future__ import annotations

import argparse
import json
import sys

from capsule.cli.commands import repo_from_args
from capsule.cli.edge import parse_patch, read_from_clipboard, stamp_by
from capsule.cli.formatting import Payload
from capsule.engine import Engine, Event, SchemaError

NAME = "apply"
HELP = "Apply a CAPSULE-PATCH block."


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--clip", action="store_true")
    parser.add_argument("--tool", default="web")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")


def run(args: argparse.Namespace) -> Payload:
    text = _read_input(args)
    parsed = parse_patch(text)
    by = stamp_by(args.tool)
    engine = Engine(repo_from_args(args))
    if args.dry_run:
        applied_ids, skipped = _dry_run_summary(engine.log(), parsed.events)
        event_count = len(engine.log())
        return {
            "_text": (
                f"Would apply {len(applied_ids)}, skip {len(skipped)} "
                f"({event_count} current events)."
            ),
            "_json": {
                "applied": applied_ids,
                "skipped": skipped,
                "event_count": event_count,
                "by": by,
                "dry_run": True,
            },
        }
    applied = engine.apply_events(list(parsed.events), by=by)
    applied_ids = [event.id for event in applied]
    applied_set = set(applied_ids)
    skipped = [event.id for event in parsed.events if event.id not in applied_set]
    event_count = len(engine.log())
    return {
        "_text": f"Applied {len(applied_ids)}, skipped {len(skipped)} ({event_count} events).",
        "_json": {
            "applied": applied_ids,
            "skipped": skipped,
            "event_count": event_count,
            "by": by,
            "dry_run": False,
        },
    }


def _read_input(args: argparse.Namespace) -> str:
    if not args.clip:
        return sys.stdin.read()
    pasted = read_from_clipboard()
    if pasted is not None:
        return pasted
    print("capsule: clipboard unavailable; reading patch from stdin", file=sys.stderr)
    return sys.stdin.read()


def _dry_run_summary(
    existing: list[Event], incoming: tuple[Event, ...]
) -> tuple[list[str], list[str]]:
    content_by_id = {event.id: _content_key(event) for event in existing}
    applied: list[str] = []
    skipped: list[str] = []
    for event in incoming:
        content_key = _content_key(event)
        previous = content_by_id.get(event.id)
        if previous is not None:
            if previous != content_key:
                raise SchemaError("patch id collides with different content")
            skipped.append(event.id)
            continue
        content_by_id[event.id] = content_key
        applied.append(event.id)
    return applied, skipped


def _content_key(event: Event) -> str:
    obj = json.loads(event.to_jsonl())
    if not isinstance(obj, dict):
        raise SchemaError("event must be an object")
    obj.pop("at", None)
    obj.pop("by", None)
    obj.pop("verified", None)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
