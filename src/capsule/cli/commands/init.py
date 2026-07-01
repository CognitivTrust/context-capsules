"""capsule init."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capsule.cli.commands import repo_from_args
from capsule.cli.edge import (
    DrafterError,
    GitHeuristicDrafter,
    IntentDraft,
    read_commits,
    redact,
    select_drafter,
)
from capsule.cli.formatting import Payload
from capsule.engine import CapsuleError, Engine, Event
from capsule.store import CapsulePaths, Store

NAME = "init"
HELP = "Initialize capsule."


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--draft", choices=["git", "llm", "none"], default="git")
    parser.add_argument("--no-git", action="store_true", dest="no_git")
    parser.add_argument("--model", default=None)
    parser.add_argument("--by", default="cli")
    parser.add_argument("--force", action="store_true")


def run(args: argparse.Namespace) -> Payload:
    repo = repo_from_args(args)
    paths = CapsulePaths.for_repo(repo)
    store = Store(paths)
    existed = store.exists()
    if existed and not args.force:
        raise CapsuleError("capsule already exists here — run `capsule load`")
    engine = Engine(repo)
    projection = engine.init()
    intent_event: Event | None = None
    draft_source = "none"
    commit_count = 0
    if args.draft != "none":
        commits = [] if args.no_git else read_commits(repo)
        commit_count = len(commits)
        drafter, notice = select_drafter(
            draft_mode=args.draft,
            model=args.model,
            verbose=args.verbose,
        )
        if notice is not None:
            print(f"capsule: {notice}", file=sys.stderr)
        try:
            draft = drafter.draft(commits, repo)
        except DrafterError as exc:
            print(f"capsule: {exc}; fell back to git heuristic.", file=sys.stderr)
            draft = GitHeuristicDrafter().draft(commits, repo)
        draft_source = draft.source
        intent_event = engine.record_intent(
            redact(draft.objective),
            constraints=[redact(item) for item in draft.constraints],
            acceptance=[],
            by=args.by,
            current_understanding=_current_understanding(draft),
            invariants=[],
        )
    message = _message(paths.capsule_dir, args.draft, commit_count)
    event_count = projection.event_count + (1 if intent_event is not None else 0)
    return {
        "_text": message,
        "_json": {
            "capsule_dir": str(paths.capsule_dir),
            "event_count": event_count,
            "draft_source": draft_source,
            "intent_id": None if intent_event is None else intent_event.id,
        },
    }


def _current_understanding(draft: IntentDraft) -> list[str]:
    if draft.source == "git-heuristic":
        label = "drafted from git history — review and correct"
    else:
        label = f"drafted by {draft.source} — review and correct"
    items = [label]
    items.extend(redact(item) for item in draft.current_understanding)
    return items


def _message(capsule_dir: Path, draft_mode: str, commit_count: int) -> str:
    if draft_mode == "none":
        return f"Initialized empty capsule at {capsule_dir}."
    return (
        f"Drafted capsule from {commit_count} commits. Review with `capsule show`, then keep "
        "current_understanding current as you learn the codebase."
    )
