"""Canonical CLI exit-code table the whole project binds to."""

import enum


@enum.unique
class ExitCode(enum.IntEnum):
    OK = 0
    ERROR = 1
    USAGE = 2
    NO_CAPSULE = 3
    SCHEMA = 4
    LOCK_TIMEOUT = 5
    CORRUPT_LOG = 6
    EVIDENCE_UNREADABLE = 7
