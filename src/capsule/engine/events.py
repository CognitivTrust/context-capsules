"""Frozen event value objects and canonical JSONL serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    kind: str
    ref: str
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ByObject:
    principal: str
    subagent: str | None = None
    model: str | None = None
    session: str | None = None
    task: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


ByValue = str | ByObject


@dataclass(frozen=True)
class Event:
    t: str
    id: str
    at: str
    by: ByValue | None
    objective: str | None = None
    current_understanding: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    decision: str | None = None
    rationale: str | None = None
    q: str | None = None
    closes: str | None = None
    answer: str | None = None
    note: str | None = None
    task_id: str | None = None
    for_intent: str | None = None
    closes_task: str | None = None
    outcome: str | None = None
    summary: str | None = None
    evidence: tuple[Evidence, ...] = ()
    verified: bool | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        obj: dict[str, Any] = {
            "t": self.t,
            "id": self.id,
            "at": self.at,
        }
        if self.by is not None:
            obj["by"] = by_to_jsonable(self.by)
        if self.t == "intent":
            obj["objective"] = self.objective
            _add_list_field(obj, "current_understanding", self.current_understanding)
            _add_list_field(obj, "constraints", self.constraints)
            _add_list_field(obj, "invariants", self.invariants)
            _add_list_field(obj, "acceptance", self.acceptance)
        elif self.t == "decision":
            obj["decision"] = self.decision
            obj["rationale"] = self.rationale
            _add_evidence_fields(obj, self.evidence, self.verified)
        elif self.t == "question":
            obj["q"] = self.q
        elif self.t == "resolution":
            obj["closes"] = self.closes
            obj["answer"] = self.answer
        elif self.t == "progress":
            obj["note"] = self.note
            _add_evidence_fields(obj, self.evidence, self.verified)
        elif self.t == "task_start":
            obj["task_id"] = self.task_id
            obj["objective"] = self.objective
            if self.for_intent is not None:
                obj["for_intent"] = self.for_intent
        elif self.t == "task_end":
            obj["closes_task"] = self.closes_task
            obj["outcome"] = self.outcome
            if self.summary is not None:
                obj["summary"] = self.summary
        for key, value in self.extra.items():
            obj[key] = value
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def by_to_jsonable(by: ByValue) -> str | dict[str, Any]:
    if isinstance(by, str):
        return by
    obj: dict[str, Any] = {"principal": by.principal}
    _add_optional_scalar(obj, "subagent", by.subagent)
    _add_optional_scalar(obj, "model", by.model)
    _add_optional_scalar(obj, "session", by.session)
    _add_optional_scalar(obj, "task", by.task)
    for key, value in by.extra.items():
        obj[key] = value
    return obj


def format_by(by: ByValue | None) -> str:
    if by is None:
        return "(none)"
    if isinstance(by, str):
        return by
    return json.dumps(by_to_jsonable(by), separators=(",", ":"), ensure_ascii=False)


def _add_list_field(obj: dict[str, Any], key: str, values: tuple[str, ...]) -> None:
    if values:
        obj[key] = list(values)


def _add_evidence_fields(
    obj: dict[str, Any],
    evidence: tuple[Evidence, ...],
    verified: bool | None,
) -> None:
    if not evidence:
        return
    obj["evidence"] = [_evidence_obj(item) for item in evidence]
    if verified is not None:
        obj["verified"] = verified


def _add_optional_scalar(obj: dict[str, Any], key: str, value: str | None) -> None:
    if value is not None:
        obj[key] = value


def _evidence_obj(evidence: Evidence) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "kind": evidence.kind,
        "ref": evidence.ref,
    }
    for key, value in evidence.extra.items():
        obj[key] = value
    return obj
