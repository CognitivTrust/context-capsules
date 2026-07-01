"""CLI-edge evidence token parsing."""

from __future__ import annotations

import argparse

from capsule.engine import Evidence

_ERROR_MESSAGE = "evidence must be KIND:REF, e.g. file:src/app.py"


def parse_evidence(token: str) -> Evidence:
    index = token.find(":")
    if index <= 0 or index == len(token) - 1:
        raise argparse.ArgumentTypeError(_ERROR_MESSAGE)
    return Evidence(kind=token[:index], ref=token[index + 1 :])
