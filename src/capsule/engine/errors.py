"""Typed engine and store errors."""

from pathlib import Path


class CapsuleError(Exception):
    """Base for all engine/store errors."""


class NoCapsule(CapsuleError):
    """Raised when a repo has no capsule yet."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"no capsule at {path} — run `capsule init`")


class SchemaError(CapsuleError):
    """Raised when an event fails schema validation."""


class LockTimeout(CapsuleError):
    """Raised when the capsule lock cannot be acquired in time."""


class CorruptLogLine(CapsuleError):
    """Raised when a non-final committed log line is corrupt."""


class EvidenceUnreadable(CapsuleError):
    """Reserved for a later phase."""


class CapsuleWarning(UserWarning):
    """Raised for non-fatal capsule conditions."""
