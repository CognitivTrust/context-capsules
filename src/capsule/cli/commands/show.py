"""capsule show."""

from __future__ import annotations

import argparse

from capsule.cli.commands import repo_from_args
from capsule.cli.formatting import Payload
from capsule.engine import Engine

NAME = "show"
HELP = "Render the capsule markdown."


def configure(parser: argparse.ArgumentParser) -> None:
    return None


def run(args: argparse.Namespace) -> Payload:
    capsule_md = Engine(repo_from_args(args)).render()
    return {
        "_text": capsule_md,
        "_json": {"markdown": capsule_md},
    }
