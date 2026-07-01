"""Shared secret redaction helpers for authored free-text content."""

from __future__ import annotations

import re

_KEY_MASK = "[REDACTED]"
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),
)


def redact(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(_KEY_MASK, redacted)
    return redacted
