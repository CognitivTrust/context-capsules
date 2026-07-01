"""Evidence verification seam."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import SplitResult, urlsplit

from capsule.engine.events import Evidence


@runtime_checkable
class EvidenceVerifier(Protocol):
    kind: str

    def verify(self, ref: str, repo: Path) -> bool: ...


class VerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: dict[str, EvidenceVerifier] = {}

    def register(self, verifier: EvidenceVerifier) -> None:
        self._verifiers[verifier.kind] = verifier

    def get(self, kind: str) -> EvidenceVerifier | None:
        return self._verifiers.get(kind)

    def verify_all(self, evidence: tuple[Evidence, ...], repo: Path) -> bool:
        for item in evidence:
            verifier = self.get(item.kind)
            if verifier is None:
                return False
            if not verifier.verify(item.ref, repo):
                return False
        return True


class FileEvidenceVerifier:
    kind = "file"

    def verify(self, ref: str, repo: Path) -> bool:
        path = _repo_path(ref, repo)
        return path is not None and path.exists()


class CommitEvidenceVerifier:
    kind = "commit"

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], bool] = {}

    def verify(self, ref: str, repo: Path) -> bool:
        cache_key = (_repo_cache_key(repo), ref)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    os.fspath(repo),
                    "cat-file",
                    "-e",
                    f"{ref}^{{commit}}",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except OSError:
            verified = False
        else:
            verified = result.returncode == 0
        self._cache[cache_key] = verified
        return verified


class TestEvidenceVerifier:
    kind = "test"

    def verify(self, ref: str, repo: Path) -> bool:
        file_ref = ref.split("::", 1)[0]
        path = _repo_path(file_ref, repo)
        return path is not None and path.exists()


class UrlEvidenceVerifier:
    kind = "url"

    def verify(self, ref: str, repo: Path) -> bool:
        del repo
        parsed = urlsplit(ref)
        return _is_supported_url(parsed)


def default_registry() -> VerifierRegistry:
    registry = VerifierRegistry()
    registry.register(FileEvidenceVerifier())
    registry.register(CommitEvidenceVerifier())
    registry.register(TestEvidenceVerifier())
    registry.register(UrlEvidenceVerifier())
    return registry


def _repo_path(ref: str, repo: Path) -> Path | None:
    candidate = Path(ref.replace("\\", "/"))
    if candidate.is_absolute() or candidate.drive != "" or candidate.root != "":
        return None
    root = repo.resolve()
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _repo_cache_key(repo: Path) -> str:
    return os.path.normcase(os.fspath(repo.resolve()))


def _is_supported_url(parsed: SplitResult) -> bool:
    return parsed.scheme in {"http", "https"} and parsed.netloc != ""
