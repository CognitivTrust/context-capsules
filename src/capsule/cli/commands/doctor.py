"""capsule doctor."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

from capsule.cli.commands import repo_from_args
from capsule.cli.formatting import Payload
from capsule.engine import CapsuleError, CorruptLogLine, Event, SchemaError
from capsule.engine.fold import fold, ordered_events
from capsule.store import CapsulePaths, Store

NAME = "doctor"
HELP = "Report local capsule health."
STALE_UNDERSTANDING_THRESHOLD: int = 5


@dataclass(frozen=True)
class GitStatus:
    available: bool
    version: str | None


@dataclass(frozen=True)
class CapsuleStatus:
    capsule_exists: bool
    event_count: int | None
    open_tasks: int
    torn: bool
    render_exists: bool
    lock_exists: bool
    log_error: str | None
    log_error_kind: str | None
    warnings: tuple[str, ...]


class PythonPayload(TypedDict):
    version: str
    supported: bool


class GitPayload(TypedDict):
    available: bool
    version: str | None


class DoctorPayload(TypedDict, total=False):
    repo: str
    python: PythonPayload
    capsule_exists: bool
    event_count: int | None
    torn: bool
    render_exists: bool
    lock_exists: bool
    git: GitPayload
    warnings: list[str]
    log_error: str
    log_error_kind: str


def configure(_parser: argparse.ArgumentParser) -> None:
    return None


def run(args: argparse.Namespace) -> Payload:
    repo = repo_from_args(args)
    git = _git_status()
    capsule = _capsule_status(CapsulePaths.for_repo(repo))
    python_version = _python_version()
    payload: DoctorPayload = {
        "repo": str(repo),
        "python": {
            "version": python_version,
            "supported": sys.version_info >= (3, 11),
        },
        "capsule_exists": capsule.capsule_exists,
        "event_count": capsule.event_count,
        "torn": capsule.torn,
        "render_exists": capsule.render_exists,
        "lock_exists": capsule.lock_exists,
        "git": {
            "available": git.available,
            "version": git.version,
        },
        "warnings": list(capsule.warnings),
    }
    if capsule.log_error is not None:
        payload["log_error"] = capsule.log_error
        if capsule.log_error_kind is not None:
            payload["log_error_kind"] = capsule.log_error_kind
    return {
        "_text": _doctor_text(payload, open_tasks=capsule.open_tasks),
        "_json": payload,
    }


def _capsule_status(paths: CapsulePaths) -> CapsuleStatus:
    store = Store(paths)
    capsule_exists = store.exists()
    render_exists = paths.render.exists() or paths.render.is_symlink()
    lock_exists = paths.lock.exists() or paths.lock.is_symlink()
    if not capsule_exists:
        return CapsuleStatus(
            capsule_exists=False,
            event_count=0,
            open_tasks=0,
            torn=False,
            render_exists=render_exists,
            lock_exists=lock_exists,
            log_error=None,
            log_error_kind=None,
            warnings=(),
        )
    warnings: list[str] = []
    try:
        read_result = store.read_events()
    except CorruptLogLine as exc:
        return _log_error_status(
            exc, "corrupt", render_exists=render_exists, lock_exists=lock_exists
        )
    except SchemaError as exc:
        return _log_error_status(
            exc, "schema", render_exists=render_exists, lock_exists=lock_exists
        )
    except CapsuleError as exc:
        return _log_error_status(exc, "error", render_exists=render_exists, lock_exists=lock_exists)
    if read_result.torn is not None:
        warnings.append("torn final log region detected")
    stale_warning = _stale_understanding_warning(read_result.events)
    if stale_warning is not None:
        warnings.append(stale_warning)
    projection = fold(read_result.events)
    return CapsuleStatus(
        capsule_exists=True,
        event_count=len(read_result.events),
        open_tasks=len(projection.open_tasks),
        torn=read_result.torn is not None,
        render_exists=render_exists,
        lock_exists=lock_exists,
        log_error=None,
        log_error_kind=None,
        warnings=tuple(warnings),
    )


def _log_error_status(
    exc: CapsuleError,
    kind: str,
    *,
    render_exists: bool,
    lock_exists: bool,
) -> CapsuleStatus:
    return CapsuleStatus(
        capsule_exists=True,
        event_count=None,
        open_tasks=0,
        torn=False,
        render_exists=render_exists,
        lock_exists=lock_exists,
        log_error=str(exc),
        log_error_kind=kind,
        warnings=(),
    )


def _git_status() -> GitStatus:
    try:
        result = subprocess.run(
            ["git", "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return GitStatus(available=False, version=None)
    if result.returncode != 0:
        return GitStatus(available=False, version=None)
    version = result.stdout.strip() or result.stderr.strip() or None
    return GitStatus(available=True, version=version)


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _doctor_text(payload: DoctorPayload, *, open_tasks: int) -> str:
    git = payload["git"]
    python = payload["python"]
    warnings = payload["warnings"]
    lines = [
        f"Repo: {payload['repo']}",
        f"Python: {python['version']} (>=3.11: {python['supported']})",
        f"Capsule exists: {payload['capsule_exists']}",
        f"Events: {payload['event_count']}",
        f"Open Tasks: {open_tasks}",
        f"Torn log tail: {payload['torn']}",
        f"Render exists: {payload['render_exists']}",
        f"Lock exists: {payload['lock_exists']}",
        f"Git available: {git['available']}",
    ]
    if git["version"] is not None:
        lines.append(f"Git version: {git['version']}")
    if "log_error" in payload:
        kind = payload.get("log_error_kind", "error")
        lines.append(f"Log error [{kind}]: {payload['log_error']}")
        lines.append(_log_error_hint(kind))
    if warnings:
        lines.append("Warnings: " + "; ".join(str(item) for item in warnings))
    return os.linesep.join(lines)


def _log_error_hint(kind: str) -> str:
    if kind == "schema":
        return (
            "Hint: a log line is valid JSON but violates the event schema — "
            "this only happens from an edit outside the CLI. Restore .capsule/log.jsonl "
            "from version control or revert the named line; do not hand-edit it to guess a fix."
        )
    if kind == "corrupt":
        return (
            "Hint: a log line is structurally damaged (not valid JSON). Restore "
            ".capsule/log.jsonl from version control or remove the damaged line."
        )
    return "Hint: the log could not be read; restore .capsule/log.jsonl from version control."


def _stale_understanding_warning(events: Sequence[Event]) -> str | None:
    ordered = ordered_events(events)
    last_understanding = _last_understanding_event(ordered)
    if last_understanding is None:
        count = _decision_progress_count(ordered)
        if count == 0:
            return None
        return (
            "current_understanding has never been set, but the log has "
            f"{count} decision/progress events — record an intent with "
            "--current-understanding so agents inherit current state"
        )
    last_index, event = last_understanding
    count = _decision_progress_count(ordered[last_index + 1 :])
    if count < STALE_UNDERSTANDING_THRESHOLD:
        return None
    return (
        "current_understanding may be stale: last set by "
        f"{event.id} at {event.at}, but {count} decision/progress events "
        "recorded since — refresh it by recording a new intent with "
        "--current-understanding"
    )


def _last_understanding_event(events: Sequence[Event]) -> tuple[int, Event] | None:
    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if event.t == "intent" and event.current_understanding:
            return index, event
    return None


def _decision_progress_count(events: Sequence[Event]) -> int:
    return sum(1 for event in events if event.t in {"decision", "progress"})
