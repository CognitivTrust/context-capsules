"""capsule CLI root: parser construction, command registry, and dispatch."""

import argparse
import pathlib
import sys
from collections.abc import Callable
from dataclasses import dataclass

from capsule import __version__
from capsule.cli.commands import global_flags_parent
from capsule.cli.formatting import Payload, format_output
from capsule.engine import (
    CapsuleError,
    CorruptLogLine,
    EvidenceUnreadable,
    LockTimeout,
    NoCapsule,
    SchemaError,
)
from capsule.exit_codes import ExitCode


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    configure: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], Payload]


def _global_flag_defaults() -> argparse.ArgumentParser:
    """Top-level parent establishing the real defaults for global flags.

    Every other level (subcommands, sub-subcommands) attaches
    ``global_flags_parent()`` instead, whose flags default to
    ``argparse.SUPPRESS`` so they don't clobber a value already supplied at
    another level.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--format", choices=["text", "json"], default="text", dest="format")
    parent.add_argument(
        "--repo",
        type=pathlib.Path,
        default=None,
        dest="repo",
        help="Repository whose .capsule/ should be used.",
    )
    parent.add_argument("--verbose", action="store_true", default=False, dest="verbose")
    return parent


import capsule.cli.commands.apply as apply_command  # noqa: E402
import capsule.cli.commands.context as context_command  # noqa: E402
import capsule.cli.commands.doctor as doctor_command  # noqa: E402
import capsule.cli.commands.init as init_command  # noqa: E402
import capsule.cli.commands.load as load_command  # noqa: E402
import capsule.cli.commands.log as log_command  # noqa: E402
import capsule.cli.commands.record as record_command  # noqa: E402
import capsule.cli.commands.show as show_command  # noqa: E402
import capsule.cli.commands.task as task_command  # noqa: E402

REGISTRY: tuple[Command, ...] = (
    Command(
        name=init_command.NAME,
        help=init_command.HELP,
        configure=init_command.configure,
        run=init_command.run,
    ),
    Command(
        name=load_command.NAME,
        help=load_command.HELP,
        configure=load_command.configure,
        run=load_command.run,
    ),
    Command(
        name=show_command.NAME,
        help=show_command.HELP,
        configure=show_command.configure,
        run=show_command.run,
    ),
    Command(
        name=doctor_command.NAME,
        help=doctor_command.HELP,
        configure=doctor_command.configure,
        run=doctor_command.run,
    ),
    Command(
        name=record_command.NAME,
        help=record_command.HELP,
        configure=record_command.configure,
        run=record_command.run,
    ),
    Command(
        name=task_command.NAME,
        help=task_command.HELP,
        configure=task_command.configure,
        run=task_command.run,
    ),
    Command(
        name=log_command.NAME,
        help=log_command.HELP,
        configure=log_command.configure,
        run=log_command.run,
    ),
    Command(
        name=context_command.NAME,
        help=context_command.HELP,
        configure=context_command.configure,
        run=context_command.run,
    ),
    Command(
        name=apply_command.NAME,
        help=apply_command.HELP,
        configure=apply_command.configure,
        run=apply_command.run,
    ),
)

_EXIT_FOR_ERROR: tuple[tuple[type[CapsuleError], ExitCode], ...] = (
    (NoCapsule, ExitCode.NO_CAPSULE),
    (SchemaError, ExitCode.SCHEMA),
    (LockTimeout, ExitCode.LOCK_TIMEOUT),
    (CorruptLogLine, ExitCode.CORRUPT_LOG),
    (EvidenceUnreadable, ExitCode.EVIDENCE_UNREADABLE),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capsule", parents=[_global_flag_defaults()])
    parser.add_argument(
        "--version",
        action="version",
        version=f"capsule {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for cmd in REGISTRY:
        subparser = subparsers.add_parser(cmd.name, help=cmd.help, parents=[global_flags_parent()])
        cmd.configure(subparser)
        subparser.set_defaults(_command=cmd)
    return parser


def _configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    _configure_output_encoding()
    minimum = (3, 11)
    if sys.version_info < minimum:
        found = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(
            "capsule requires Python 3.11+ "
            f"(found {found}); on macOS install a newer Python via Homebrew/pyenv",
            file=sys.stderr,
        )
        return int(ExitCode.ERROR)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args._command.run(args)
        if args.format == "json":
            print(format_output(payload.get("_json", _public(payload)), "json"))
        else:
            text = payload.get("_text")
            if text is None:
                print(format_output(_public(payload), "text"))
            elif text != "":
                print(text)
        return int(ExitCode.OK)
    except CapsuleError as exc:
        if getattr(args, "verbose", False):
            raise
        print(f"capsule: error: {exc}", file=sys.stderr)
        return int(_exit_code_for(exc))
    except Exception as exc:
        if getattr(args, "verbose", False):
            raise
        print(f"capsule: error: {exc}", file=sys.stderr)
        return int(ExitCode.ERROR)


def _public(payload: Payload) -> Payload:
    public_payload: Payload = {}
    for key, value in payload.items():
        if not key.startswith("_"):
            public_payload[key] = value
    return public_payload


def _exit_code_for(exc: CapsuleError) -> ExitCode:
    for error_type, exit_code in _EXIT_FOR_ERROR:
        if isinstance(exc, error_type):
            return exit_code
    return ExitCode.ERROR
