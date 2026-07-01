"""CAPSULE-PATCH parsing and validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from capsule.engine import Event, SchemaError
from capsule.engine.schema import from_obj

FENCE_INFO = "capsule-patch"
VERSION_PREFIX = "capsule-patch/"
SUPPORTED_MAJOR = "v0"
_SENTINEL_AT = "1970-01-01T00:00:00Z"

_OPEN_FENCE_RE = re.compile(r"```capsule-patch[ \t]*\r?\n", re.MULTILINE)


@dataclass(frozen=True)
class ParsedPatch:
    version: str
    events: tuple[Event, ...]


def parse_patch(text: str) -> ParsedPatch:
    body = _extract_body(text)
    obj = _parse_object(body)
    version = _parse_version(obj)
    raw_events = obj.get("events")
    if not isinstance(raw_events, list):
        raise SchemaError("'events' must be a list")
    events = tuple(_event_from_patch_entry(item) for item in raw_events)
    return ParsedPatch(version=version, events=events)


def stamp_by(tool: str) -> str:
    return "web" if tool == "web" else f"{tool}-web"


def _extract_body(text: str) -> str:
    match = _OPEN_FENCE_RE.search(text)
    if match is None:
        raise SchemaError("no CAPSULE-PATCH block found")
    start = match.end()
    fence_index = text.find("```", start)
    if fence_index == -1:
        raise SchemaError("the CAPSULE-PATCH block looks incomplete")
    return text[start:fence_index]


def _parse_object(body: str) -> Mapping[str, Any]:
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid CAPSULE-PATCH JSON: {exc.msg}") from exc
    if not isinstance(obj, Mapping):
        raise SchemaError("CAPSULE-PATCH body must be a JSON object")
    return obj


def _parse_version(obj: Mapping[str, Any]) -> str:
    version = obj.get("version")
    if not isinstance(version, str) or version == "":
        raise SchemaError("'version' must be a non-empty string")
    if not version.startswith(VERSION_PREFIX):
        raise SchemaError(f"unsupported CAPSULE-PATCH version: {version!r}")
    major = version[len(VERSION_PREFIX) :].split(".", 1)[0]
    if major != SUPPORTED_MAJOR:
        raise SchemaError(f"unsupported CAPSULE-PATCH version: {version!r}")
    return version


def _event_from_patch_entry(item: object) -> Event:
    if not isinstance(item, Mapping):
        raise SchemaError("patch events must be objects")
    event_id = item.get("id")
    if not isinstance(event_id, str) or event_id == "":
        raise SchemaError("'id' must be a non-empty string")
    candidate = dict(item)
    candidate.pop("at", None)
    candidate.pop("by", None)
    candidate.pop("verified", None)
    candidate["at"] = _SENTINEL_AT
    evidence = candidate.get("evidence")
    if isinstance(evidence, list) and evidence:
        candidate["verified"] = False
    return from_obj(candidate)
