"""capsule subcommand handlers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from capsule.engine import ByObject, ByValue, SchemaError


def repo_from_args(args: argparse.Namespace) -> Path:
    return (args.repo if args.repo is not None else Path.cwd()).resolve()


def add_by_arguments(parser: argparse.ArgumentParser, *, default: str | None = None) -> None:
    parser.add_argument("--by", default=None)
    parser.add_argument("--by-principal", dest="by_principal", default=None)
    parser.add_argument("--by-subagent", dest="by_subagent", default=None)
    parser.add_argument("--by-model", dest="by_model", default=None)
    parser.add_argument("--by-session", dest="by_session", default=None)
    parser.add_argument("--by-task", dest="by_task", default=None)
    parser.set_defaults(_by_default=default)


def resolve_by(args: argparse.Namespace) -> ByValue:
    by = cast(str | None, getattr(args, "by", None))
    principal = getattr(args, "by_principal", None)
    subagent = getattr(args, "by_subagent", None)
    model = getattr(args, "by_model", None)
    session = getattr(args, "by_session", None)
    task = getattr(args, "by_task", None)
    default_by = cast(str | None, getattr(args, "_by_default", None))
    has_structured = any(value is not None for value in (principal, subagent, model, session, task))
    if not has_structured:
        if by is not None:
            return by
        if default_by is None:
            raise SchemaError("missing by principal")
        return default_by
    if by is not None:
        if principal is not None and principal != by:
            raise SchemaError("--by and --by-principal must match when both are provided")
        principal = by if principal is None else principal
    if principal is None:
        raise SchemaError("structured by fields require --by-principal or --by")
    return ByObject(
        principal=principal,
        subagent=subagent,
        model=model,
        session=session,
        task=task,
    )
