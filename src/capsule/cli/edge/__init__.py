"""Public edge-layer exports for CLI helpers."""

from capsule.cli.edge.clipboard import copy_to_clipboard, read_from_clipboard
from capsule.cli.edge.evidence import parse_evidence
from capsule.cli.edge.patch import (
    FENCE_INFO,
    SUPPORTED_MAJOR,
    VERSION_PREFIX,
    ParsedPatch,
    parse_patch,
    stamp_by,
)
from capsule.redaction import redact

__all__ = [
    "FENCE_INFO",
    "ParsedPatch",
    "SUPPORTED_MAJOR",
    "VERSION_PREFIX",
    "copy_to_clipboard",
    "parse_evidence",
    "parse_patch",
    "read_from_clipboard",
    "redact",
    "stamp_by",
]
