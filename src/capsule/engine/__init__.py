"""Public engine exports."""

from typing import TYPE_CHECKING

from capsule.engine.errors import (
    CapsuleError,
    CapsuleWarning,
    CorruptLogLine,
    EvidenceUnreadable,
    LockTimeout,
    NoCapsule,
    SchemaError,
)
from capsule.engine.events import ByObject, ByValue, Event, Evidence
from capsule.engine.fold import DecisionView, OpenTaskView, ProgressView, Projection, QuestionView
from capsule.engine.verify import EvidenceVerifier, VerifierRegistry

if TYPE_CHECKING:
    from capsule.engine.engine import Engine

__all__ = [
    "ByObject",
    "ByValue",
    "CapsuleError",
    "CapsuleWarning",
    "CorruptLogLine",
    "DecisionView",
    "Engine",
    "Event",
    "Evidence",
    "EvidenceUnreadable",
    "EvidenceVerifier",
    "LockTimeout",
    "NoCapsule",
    "OpenTaskView",
    "ProgressView",
    "Projection",
    "QuestionView",
    "SchemaError",
    "VerifierRegistry",
]


def __getattr__(name: str) -> object:
    if name == "Engine":
        from capsule.engine.engine import Engine as engine_cls

        return engine_cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
