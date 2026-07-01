"""Local capsule store operations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capsule.engine.errors import CapsuleError, CorruptLogLine, SchemaError
from capsule.engine.events import Event
from capsule.engine.schema import from_obj
from capsule.store.paths import CapsulePaths


def _assert_under_root(path: Path, root: Path) -> None:
    root_resolved = root.resolve()
    try:
        path.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise CapsuleError(
            f"capsule path {path} resolves outside repo root {root_resolved}"
        ) from exc


def _assert_capsule_layout_safe(paths: CapsulePaths) -> None:
    _assert_under_root(paths.capsule_dir, paths.root)
    for path in (paths.log, paths.render, paths.lock):
        if path.exists() or path.is_symlink():
            _assert_under_root(path, paths.root)


@dataclass(frozen=True)
class TornRegion:
    offset: int
    raw: bytes


@dataclass(frozen=True)
class ReadResult:
    events: tuple[Event, ...]
    torn: TornRegion | None


class Store:
    def __init__(self, paths: CapsulePaths) -> None:
        self.paths = paths

    def exists(self) -> bool:
        return self.paths.exists()

    def ensure_layout_safe(self) -> None:
        _assert_capsule_layout_safe(self.paths)

    def create(self) -> None:
        self.ensure_layout_safe()
        try:
            self.paths.capsule_dir.mkdir(parents=True, exist_ok=True)
            if not self.paths.log.exists():
                self.paths.log.write_text("", encoding="utf-8", newline="")
        except OSError as exc:
            raise CapsuleError(
                f"failed to create capsule at {self.paths.capsule_dir}: {exc}"
            ) from exc

    def read_events(self) -> ReadResult:
        self.ensure_layout_safe()
        if not self.paths.log.exists():
            return ReadResult((), None)
        try:
            data = self.paths.log.read_bytes()
        except OSError as exc:
            raise CapsuleError(f"failed to read {self.paths.log}: {exc}") from exc
        if not data:
            return ReadResult((), None)

        ends_with_newline = data.endswith(b"\n")
        parts = data.split(b"\n")
        terminated = parts[:-1]
        trailing = None if ends_with_newline or not parts[-1] else parts[-1]
        events: list[Event] = []
        offset = 0

        for index, raw_line in enumerate(terminated):
            line_start = offset
            offset += len(raw_line) + 1
            try:
                events.append(_parse_line(raw_line))
            except SchemaError as exc:
                # A fully written (newline-terminated) line that parses as JSON but
                # fails the event schema is a contract violation, not byte corruption,
                # and must surface loudly — never be quarantined as a torn tail.
                raise SchemaError(
                    f"invalid event in {self.paths.log} "
                    f"at line {index + 1} (byte offset {line_start}): {exc}"
                ) from exc
            except _LineParseError as exc:
                raise CorruptLogLine(
                    f"corrupt log line in {self.paths.log} "
                    f"at line {index + 1} (byte offset {line_start}): {exc}"
                ) from exc

        if trailing is not None:
            return ReadResult(tuple(events), TornRegion(offset, trailing))
        return ReadResult(tuple(events), None)

    def quarantine_and_truncate(self, torn: TornRegion, ts: str) -> Path:
        self.ensure_layout_safe()
        corrupt_path = self.paths.capsule_dir / f"log.jsonl.corrupt-{ts}"
        try:
            corrupt_path.write_bytes(torn.raw)
            with self.paths.log.open("r+b") as handle:
                handle.truncate(torn.offset)
        except OSError as exc:
            raise CapsuleError(f"failed to quarantine torn log region: {exc}") from exc
        return corrupt_path

    def append_line(self, jsonl_line: str) -> None:
        self.ensure_layout_safe()
        try:
            with self.paths.log.open("ab") as handle:
                handle.write((jsonl_line + "\n").encode("utf-8"))
                handle.flush()
        except OSError as exc:
            raise CapsuleError(f"failed to append to {self.paths.log}: {exc}") from exc

    def write_render(self, text: str) -> None:
        self.ensure_layout_safe()
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                dir=self.paths.capsule_dir,
                delete=False,
            ) as handle:
                handle.write(text)
                tmp_name = handle.name
            os.replace(tmp_name, self.paths.render)
        except OSError as exc:
            raise CapsuleError(f"failed to write render at {self.paths.render}: {exc}") from exc

    def stat_key(self) -> tuple[str, int, int]:
        try:
            if not self.paths.log.exists():
                return (str(self.paths.log), 0, 0)
            stat = self.paths.log.stat()
        except OSError as exc:
            raise CapsuleError(f"failed to stat {self.paths.log}: {exc}") from exc
        return (str(self.paths.log), stat.st_size, stat.st_mtime_ns)


class _LineParseError(Exception):
    pass


def _parse_line(raw_line: bytes) -> Event:
    try:
        text = raw_line.decode("utf-8")
        obj = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _LineParseError(str(exc)) from exc
    return from_obj(_as_mapping(obj))


def _as_mapping(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    raise SchemaError("event must be an object")
