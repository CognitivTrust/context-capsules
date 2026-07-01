"""Public edge-layer exports for CLI helpers."""

from capsule.cli.edge.clipboard import copy_to_clipboard, read_from_clipboard
from capsule.cli.edge.drafter import (
    DEFAULT_BASE_URL,
    Drafter,
    DrafterError,
    GitHeuristicDrafter,
    IntentDraft,
    LLMDrafter,
    read_api_key,
    select_drafter,
)
from capsule.cli.edge.evidence import parse_evidence
from capsule.cli.edge.git import CommitSummary, read_commits
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
    "CommitSummary",
    "DEFAULT_BASE_URL",
    "Drafter",
    "DrafterError",
    "FENCE_INFO",
    "GitHeuristicDrafter",
    "IntentDraft",
    "LLMDrafter",
    "ParsedPatch",
    "SUPPORTED_MAJOR",
    "VERSION_PREFIX",
    "copy_to_clipboard",
    "parse_evidence",
    "parse_patch",
    "read_api_key",
    "read_commits",
    "read_from_clipboard",
    "redact",
    "select_drafter",
    "stamp_by",
]
