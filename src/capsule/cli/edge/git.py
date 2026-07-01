"""Read-only git history helpers for cold-start drafting."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommitSummary:
    short_hash: str
    subject: str
    paths: tuple[str, ...]


def read_commits(repo: Path, *, limit: int = 50) -> list[CommitSummary]:
    if limit <= 0:
        return []
    argv = [
        "git",
        "-C",
        str(repo),
        "log",
        f"-n{limit}",
        "--name-only",
        "--format=%h%x1f%s%x1e",
    ]
    try:
        completed = subprocess.run(
            argv,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return []
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    return _parse_git_log(completed.stdout)


def _parse_git_log(output: str) -> list[CommitSummary]:
    summaries: list[CommitSummary] = []
    for chunk in output.split("\x1e"):
        if chunk == "":
            continue
        lines = [line for line in chunk.splitlines() if line != ""]
        if not lines:
            continue
        header = lines[0]
        short_hash, sep, subject = header.partition("\x1f")
        if sep == "":
            continue
        summaries.append(
            CommitSummary(
                short_hash=short_hash,
                subject=subject,
                paths=tuple(lines[1:]),
            )
        )
    return summaries
