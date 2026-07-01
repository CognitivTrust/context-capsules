"""Capsule path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CapsulePaths:
    root: Path
    capsule_dir: Path
    log: Path
    render: Path
    lock: Path

    @classmethod
    def for_repo(cls, repo: Path) -> CapsulePaths:
        root = Path(repo).resolve()
        capsule_dir = root / ".capsule"
        return cls(
            root=root,
            capsule_dir=capsule_dir,
            log=capsule_dir / "log.jsonl",
            render=capsule_dir / "capsule.md",
            lock=capsule_dir / ".lock",
        )

    def exists(self) -> bool:
        return self.capsule_dir.is_dir()
