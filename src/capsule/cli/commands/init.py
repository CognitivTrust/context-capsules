"""capsule init."""

from __future__ import annotations

import argparse
from pathlib import Path

from capsule.cli.commands import repo_from_args
from capsule.cli.formatting import Payload
from capsule.engine import CapsuleError, Engine
from capsule.store import CapsulePaths, Store

NAME = "init"
HELP = "Initialize capsule."


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force", action="store_true")


def run(args: argparse.Namespace) -> Payload:
    repo = repo_from_args(args)
    paths = CapsulePaths.for_repo(repo)
    store = Store(paths)
    if store.exists() and not args.force:
        raise CapsuleError("capsule already exists here — run `capsule load`")
    engine = Engine(repo)
    projection = engine.init()
    return {
        "_text": _message(paths.capsule_dir),
        "_json": {
            "capsule_dir": str(paths.capsule_dir),
            "event_count": projection.event_count,
        },
    }


def _message(capsule_dir: Path) -> str:
    return f"Initialized empty capsule at {capsule_dir}."
