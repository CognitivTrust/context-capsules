"""Capsule engine orchestration."""

from __future__ import annotations

import json
import sys
import uuid
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from capsule.engine.errors import CapsuleWarning, NoCapsule, SchemaError
from capsule.engine.events import ByValue, Event, Evidence, by_to_jsonable
from capsule.engine.fold import Projection, fold
from capsule.engine.render import render as render_projection
from capsule.engine.schema import from_obj
from capsule.engine.verify import VerifierRegistry, default_registry
from capsule.redaction import redact
from capsule.store import CapsulePaths, Store
from capsule.store.lock import capsule_lock

if TYPE_CHECKING:

    class Diff:
        pass


class Engine:
    def __init__(
        self,
        repo: Path,
        *,
        now: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
        verifiers: VerifierRegistry | None = None,
    ) -> None:
        self._paths = CapsulePaths.for_repo(repo)
        self._now = _utcnow if now is None else now
        self._new_id = _uuid_hex if new_id is None else new_id
        self._verifiers = default_registry() if verifiers is None else verifiers
        self._cache: tuple[tuple[str, int, int], Projection] | None = None

    def init(self) -> Projection:
        store = Store(self._paths)
        store.create()
        read_result = store.read_events()
        if read_result.torn is not None:
            self._warn_torn(store.paths.log)
        projection = fold(read_result.events)
        store.write_render(render_projection(projection))
        self._cache = (store.stat_key(), projection)
        return projection

    def load(self) -> Projection:
        store = self._require_store()
        return self._load_projection(store)

    def record_intent(
        self,
        objective: str,
        constraints: list[str],
        acceptance: list[str],
        *,
        by: ByValue = "cli",
        current_understanding: list[str] | None = None,
        invariants: list[str] | None = None,
    ) -> Event:
        return self._record_event(
            "intent",
            {
                "objective": objective,
                "current_understanding": list(current_understanding or []),
                "constraints": list(constraints),
                "invariants": list(invariants or []),
                "acceptance": list(acceptance),
            },
            by=by,
        )

    def record_decision(
        self,
        decision: str,
        rationale: str,
        evidence: list[Evidence],
        *,
        by: ByValue = "cli",
    ) -> Event:
        return self._record_event(
            "decision",
            {
                "decision": decision,
                "rationale": rationale,
            },
            evidence=tuple(evidence),
            by=by,
        )

    def note_question(self, q: str, *, by: ByValue = "cli") -> Event:
        return self._record_event("question", {"q": q}, by=by)

    def resolve_question(self, qid: str, answer: str, *, by: ByValue = "cli") -> Event:
        return self._record_event(
            "resolution",
            {
                "closes": qid,
                "answer": answer,
            },
            by=by,
            qid=qid,
        )

    def mark_progress(
        self,
        note: str,
        evidence: list[Evidence],
        *,
        by: ByValue = "cli",
    ) -> Event:
        return self._record_event(
            "progress",
            {
                "note": note,
            },
            evidence=tuple(evidence),
            by=by,
        )

    def start_task(
        self,
        task_id: str,
        objective: str,
        *,
        by: ByValue = "cli",
        for_intent: str | None = None,
    ) -> Event:
        return self._record_event(
            "task_start",
            {
                "task_id": task_id,
                "objective": objective,
                **({"for_intent": for_intent} if for_intent is not None else {}),
            },
            by=by,
            task_id=task_id,
        )

    def end_task(
        self,
        task_id: str,
        outcome: str,
        *,
        by: ByValue = "cli",
        summary: str | None = None,
    ) -> Event:
        authored: dict[str, object] = {
            "closes_task": task_id,
            "outcome": outcome,
        }
        if summary is not None:
            authored["summary"] = summary
        return self._record_event(
            "task_end",
            authored,
            by=by,
            closes_task=task_id,
        )

    def apply_events(self, events: list[Event], *, by: ByValue) -> list[Event]:
        store = self._require_store()
        if not events:
            return []
        store.ensure_layout_safe()
        with capsule_lock(self._paths.lock):
            read_result = store.read_events()
            if read_result.torn is not None:
                store.quarantine_and_truncate(read_result.torn, _file_ts(self._now()))
            existing = read_result.events
            timestamp = _format_at(self._now())
            content_by_id = {event.id: _content_key(event) for event in existing}
            authoritative: list[Event] = []
            for event in events:
                candidate = self._authoritative_patch_event(event, by=by, at=timestamp)
                if candidate.t == "resolution" and candidate.closes is not None:
                    _validate_question_linkage(
                        existing + tuple(authoritative),
                        candidate.closes,
                    )
                if candidate.t == "task_start" and candidate.task_id is not None:
                    _validate_task_start_uniqueness(
                        existing + tuple(authoritative),
                        candidate.task_id,
                    )
                if candidate.t == "task_end" and candidate.closes_task is not None:
                    _validate_task_linkage(
                        existing + tuple(authoritative),
                        candidate.closes_task,
                    )
                content_key = _content_key(candidate)
                previous = content_by_id.get(candidate.id)
                if previous is not None:
                    if previous != content_key:
                        raise SchemaError("patch id collides with different content")
                    continue
                content_by_id[candidate.id] = content_key
                authoritative.append(candidate)
            if not authoritative:
                return []
            for event in authoritative:
                store.append_line(event.to_jsonl())
            projection = fold(existing + tuple(authoritative))
            store.write_render(render_projection(projection))
            self._cache = (store.stat_key(), projection)
            return authoritative

    def log(self) -> list[Event]:
        store = self._require_store()
        read_result = store.read_events()
        if read_result.torn is not None:
            self._warn_torn(store.paths.log)
        return list(read_result.events)

    def render(self) -> str:
        return render_projection(self.load())

    def diff(self, rev: str) -> Diff:
        raise NotImplementedError("diff is Phase 3")

    def revert(self, rev: str, *, by: ByValue = "cli") -> Event:
        raise NotImplementedError("revert is Phase 3")

    def _record_event(
        self,
        event_type: str,
        authored: dict[str, object],
        *,
        evidence: tuple[Evidence, ...] = (),
        by: ByValue,
        qid: str | None = None,
        task_id: str | None = None,
        closes_task: str | None = None,
    ) -> Event:
        store = self._require_store()
        verified = self._verifiers.verify_all(evidence, self._paths.root) if evidence else None
        timestamp = self._now()
        redacted_authored = _redact_authored(authored)
        candidate = self._candidate_obj(
            event_type,
            redacted_authored,
            evidence=evidence,
            verified=verified,
            by=by,
            event_id=self._new_id(),
            at=_format_at(timestamp),
        )
        event = from_obj(candidate)
        store.ensure_layout_safe()
        with capsule_lock(self._paths.lock):
            read_result = store.read_events()
            if read_result.torn is not None:
                store.quarantine_and_truncate(read_result.torn, _file_ts(self._now()))
            if qid is not None:
                _validate_question_linkage(read_result.events, qid)
            if task_id is not None:
                _validate_task_start_uniqueness(read_result.events, task_id)
            if closes_task is not None:
                _validate_task_linkage(read_result.events, closes_task)
            store.append_line(event.to_jsonl())
            projection = fold(read_result.events + (event,))
            store.write_render(render_projection(projection))
            self._cache = (store.stat_key(), projection)
        return event

    def _authoritative_patch_event(self, event: Event, *, by: ByValue, at: str) -> Event:
        authored = _redact_authored(_content_obj(event))
        verified = (
            self._verifiers.verify_all(event.evidence, self._paths.root) if event.evidence else None
        )
        authored["at"] = at
        authored["by"] = by_to_jsonable(by)
        if event.evidence:
            authored["verified"] = verified
        return from_obj(authored)

    def _candidate_obj(
        self,
        event_type: str,
        authored: dict[str, object],
        *,
        evidence: tuple[Evidence, ...],
        verified: bool | None,
        by: ByValue,
        event_id: str,
        at: str,
    ) -> dict[str, object]:
        obj: dict[str, object] = {
            "t": event_type,
            "id": event_id,
            "at": at,
            "by": by_to_jsonable(by),
        }
        for key, value in authored.items():
            obj[key] = value
        if evidence:
            obj["evidence"] = [_evidence_obj(item) for item in evidence]
            obj["verified"] = verified
        return obj

    def _require_store(self) -> Store:
        store = Store(self._paths)
        if not store.exists():
            raise NoCapsule(self._paths.capsule_dir)
        return store

    def _load_projection(self, store: Store) -> Projection:
        read_result = store.read_events()
        if read_result.torn is not None:
            self._warn_torn(store.paths.log)
        stat_key = store.stat_key()
        if self._cache is not None and self._cache[0] == stat_key:
            return self._cache[1]
        projection = fold(read_result.events)
        self._cache = (stat_key, projection)
        return projection

    def _warn_torn(self, log_path: Path) -> None:
        message = (
            f"torn final line in {log_path}; valid prefix loaded; will be quarantined on next write"
        )
        print(f"capsule: warning: {message}", file=sys.stderr)
        warnings.warn(message, CapsuleWarning, stacklevel=2)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid_hex() -> str:
    return uuid.uuid4().hex


def _format_at(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_ts(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _evidence_obj(evidence: Evidence) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "kind": evidence.kind,
        "ref": evidence.ref,
    }
    for key, value in evidence.extra.items():
        obj[key] = value
    return obj


def _content_obj(event: Event) -> dict[str, object]:
    obj = json.loads(event.to_jsonl())
    if not isinstance(obj, dict):
        raise SchemaError("event must be an object")
    stripped = dict(obj)
    stripped.pop("at", None)
    stripped.pop("by", None)
    stripped.pop("verified", None)
    return stripped


def _content_key(event: Event) -> str:
    return json.dumps(_content_obj(event), sort_keys=True, separators=(",", ":"))


def _validate_question_linkage(events: tuple[Event, ...], qid: str) -> None:
    has_question = any(event.t == "question" and event.id == qid for event in events)
    if not has_question:
        raise SchemaError(f"unknown question id: {qid!r}")
    already_closed = any(event.t == "resolution" and event.closes == qid for event in events)
    if already_closed:
        raise SchemaError(f"question already resolved: {qid!r}")


def _validate_task_linkage(events: tuple[Event, ...], task_id: str) -> None:
    has_task = any(event.t == "task_start" and event.task_id == task_id for event in events)
    if not has_task:
        raise SchemaError(f"unknown task id: {task_id!r}")


def _validate_task_start_uniqueness(events: tuple[Event, ...], task_id: str) -> None:
    already_started = any(event.t == "task_start" and event.task_id == task_id for event in events)
    if already_started:
        raise SchemaError(f"task already started: {task_id!r}")


_REDACTED_SCALAR_FIELDS: frozenset[str] = frozenset(
    {"objective", "rationale", "decision", "note", "q", "answer"}
)
_REDACTED_LIST_FIELDS: frozenset[str] = frozenset(
    {"current_understanding", "constraints", "invariants", "acceptance", "context"}
)


def _redact_authored(authored: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in authored.items():
        redacted[key] = _redact_authored_value(key, value)
    return redacted


def _redact_authored_value(key: str, value: object) -> object:
    if key in _REDACTED_SCALAR_FIELDS and isinstance(value, str):
        return redact(value)
    if key in _REDACTED_LIST_FIELDS and isinstance(value, list):
        items: list[object] = []
        for item in value:
            items.append(redact(item) if isinstance(item, str) else item)
        return items
    return value
