"""Schema validation for capsule events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from capsule.engine.errors import SchemaError
from capsule.engine.events import ByObject, ByValue, Event, Evidence

EVENT_TYPES: frozenset[str] = frozenset(
    {"intent", "decision", "question", "resolution", "progress", "task_start", "task_end"}
)
EVIDENCE_KINDS: frozenset[str] = frozenset({"file", "commit", "test", "url"})
TASK_OUTCOMES: frozenset[str] = frozenset({"completed", "abandoned", "superseded"})
_BY_KEY_ORDER: tuple[str, ...] = ("principal", "subagent", "model", "session", "task")
_BY_KEYS: frozenset[str] = frozenset(_BY_KEY_ORDER)

_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "t",
        "id",
        "at",
        "by",
        "closes",
        "verified",
        "objective",
        "current_understanding",
        "constraints",
        "invariants",
        "acceptance",
        "decision",
        "rationale",
        "evidence",
        "q",
        "answer",
        "note",
        "task_id",
        "for_intent",
        "closes_task",
        "outcome",
        "summary",
    }
)
_COMMON_FIELDS: frozenset[str] = frozenset({"t", "id", "at", "by"})
_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "intent": _COMMON_FIELDS
    | frozenset(
        {
            "objective",
            "current_understanding",
            "constraints",
            "invariants",
            "acceptance",
        }
    ),
    "decision": _COMMON_FIELDS | frozenset({"decision", "rationale", "evidence", "verified"}),
    "question": _COMMON_FIELDS | frozenset({"q"}),
    "resolution": _COMMON_FIELDS | frozenset({"closes", "answer"}),
    "progress": _COMMON_FIELDS | frozenset({"note", "evidence", "verified"}),
    "task_start": _COMMON_FIELDS | frozenset({"task_id", "objective", "for_intent"}),
    "task_end": _COMMON_FIELDS | frozenset({"closes_task", "outcome", "summary"}),
}


def from_obj(obj: Mapping[str, Any]) -> Event:
    if not isinstance(obj, Mapping):
        raise SchemaError("event must be an object")

    event_type = _required_non_empty_str(obj, "t")
    if event_type not in EVENT_TYPES:
        raise SchemaError(f"invalid event type: {event_type!r}")

    _reject_disallowed_fields(obj, event_type)

    event_id = _required_non_empty_str(obj, "id")
    at = _required_non_empty_str(obj, "at")
    by = _parse_by(obj)
    evidence, evidence_present = _parse_evidence(obj, event_type)
    verified = _parse_verified(obj, evidence_present, evidence)
    extra = _top_level_extra(obj)

    if event_type == "intent":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            objective=_required_non_empty_str(obj, "objective"),
            current_understanding=_optional_str_list(obj, "current_understanding"),
            constraints=_optional_str_list(obj, "constraints"),
            invariants=_optional_str_list(obj, "invariants"),
            acceptance=_optional_str_list(obj, "acceptance"),
            extra=extra,
        )
    if event_type == "decision":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            decision=_required_non_empty_str(obj, "decision"),
            rationale=_required_non_empty_str(obj, "rationale"),
            evidence=evidence,
            verified=verified,
            extra=extra,
        )
    if event_type == "question":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            q=_required_non_empty_str(obj, "q"),
            extra=extra,
        )
    if event_type == "resolution":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            closes=_required_non_empty_str(obj, "closes"),
            answer=_required_non_empty_str(obj, "answer"),
            extra=extra,
        )
    if event_type == "progress":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            note=_required_non_empty_str(obj, "note"),
            evidence=evidence,
            verified=verified,
            extra=extra,
        )
    if event_type == "task_start":
        return Event(
            t=event_type,
            id=event_id,
            at=at,
            by=by,
            task_id=_required_non_empty_str(obj, "task_id"),
            objective=_required_non_empty_str(obj, "objective"),
            for_intent=_optional_str(obj, "for_intent"),
            extra=extra,
        )
    return Event(
        t=event_type,
        id=event_id,
        at=at,
        by=by,
        closes_task=_required_non_empty_str(obj, "closes_task"),
        outcome=_required_task_outcome(obj),
        summary=_optional_str(obj, "summary"),
        extra=extra,
    )


def _reject_disallowed_fields(obj: Mapping[str, Any], event_type: str) -> None:
    allowed = _ALLOWED_FIELDS[event_type]
    for key in obj:
        if key in _KNOWN_FIELDS and key not in allowed:
            raise SchemaError(f"field {key!r} is not allowed on {event_type!r}")


def _required_non_empty_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or value == "":
        raise SchemaError(f"{key!r} must be a non-empty string")
    return value


def _optional_str(obj: Mapping[str, Any], key: str) -> str | None:
    if key not in obj:
        return None
    value = obj[key]
    if not isinstance(value, str):
        raise SchemaError(f"{key!r} must be a string")
    return value


def _parse_by(obj: Mapping[str, Any]) -> ByValue | None:
    if "by" not in obj:
        return None
    value = obj["by"]
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        raise SchemaError("'by' must be a string or object")
    return _parse_by_object(value)


def _parse_by_object(obj: Mapping[str, Any]) -> ByObject:
    _validate_by_key_order(obj)
    if "principal" not in obj:
        raise SchemaError("'by.principal' is required")
    principal = _by_str(obj, "principal", required=True)
    assert principal is not None
    return ByObject(
        principal=principal,
        subagent=_by_str(obj, "subagent"),
        model=_by_str(obj, "model"),
        session=_by_str(obj, "session"),
        task=_by_str(obj, "task"),
        extra=_by_extra(obj),
    )


def _validate_by_key_order(obj: Mapping[str, Any]) -> None:
    positions = {key: index for index, key in enumerate(_BY_KEY_ORDER)}
    last_known = -1
    saw_unknown = False
    for key in obj:
        if key not in _BY_KEYS:
            saw_unknown = True
            continue
        position = positions[key]
        if saw_unknown or position < last_known:
            raise SchemaError(
                "'by' object keys must be ordered as principal, subagent, model, "
                "session, task, then extras"
            )
        last_known = position


def _by_str(obj: Mapping[str, Any], key: str, *, required: bool = False) -> str | None:
    if key not in obj:
        if required:
            raise SchemaError(f"'by.{key}' is required")
        return None
    value = obj[key]
    if not isinstance(value, str):
        raise SchemaError(f"'by.{key}' must be a string")
    return value


def _by_extra(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    extra: dict[str, Any] = {}
    for key, value in obj.items():
        if key not in _BY_KEYS:
            extra[key] = value
    return extra


def _optional_str_list(obj: Mapping[str, Any], key: str) -> tuple[str, ...]:
    if key not in obj:
        return ()
    value = obj[key]
    if not isinstance(value, list):
        raise SchemaError(f"{key!r} must be a list of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SchemaError(f"{key!r} must be a list of strings")
        items.append(item)
    return tuple(items)


def _parse_evidence(
    obj: Mapping[str, Any],
    event_type: str,
) -> tuple[tuple[Evidence, ...], bool]:
    if event_type not in {"decision", "progress"}:
        return (), False
    if "evidence" not in obj:
        return (), False
    raw = obj["evidence"]
    if not isinstance(raw, list):
        raise SchemaError("'evidence' must be a list")
    evidence: list[Evidence] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise SchemaError("evidence entries must be objects")
        kind = _required_non_empty_str(item, "kind")
        if kind not in EVIDENCE_KINDS:
            raise SchemaError(f"invalid evidence kind: {kind!r}")
        ref = _required_non_empty_str(item, "ref")
        evidence.append(Evidence(kind=kind, ref=ref, extra=_evidence_extra(item)))
    return tuple(evidence), True


def _parse_verified(
    obj: Mapping[str, Any],
    evidence_present: bool,
    evidence: tuple[Evidence, ...],
) -> bool | None:
    if "verified" not in obj:
        if evidence_present and evidence:
            raise SchemaError("'verified' is required when evidence is non-empty")
        return None
    if not evidence_present or not evidence:
        raise SchemaError("'verified' requires non-empty evidence")
    value = obj["verified"]
    if not isinstance(value, bool):
        raise SchemaError("'verified' must be a bool")
    return value


def _required_task_outcome(obj: Mapping[str, Any]) -> str:
    outcome = _required_non_empty_str(obj, "outcome")
    if outcome not in TASK_OUTCOMES:
        raise SchemaError(f"invalid task outcome: {outcome!r}")
    return outcome


def _top_level_extra(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    extra: dict[str, Any] = {}
    for key, value in obj.items():
        if key not in _KNOWN_FIELDS:
            extra[key] = value
    return extra


def _evidence_extra(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    extra: dict[str, Any] = {}
    for key, value in obj.items():
        if key not in {"kind", "ref"}:
            extra[key] = value
    return extra
