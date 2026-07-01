"""Security tests for sparse-repo cold-start file scanning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from capsule.cli.edge.drafter import _sparse_repo_signals


def test_sparse_scan_skips_readme_symlink_outside_repo(tmp_path: Path) -> None:
    """Escaping README symlink must not seed objective from outside the repo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("# Leaked Secret Title\n", encoding="utf-8")
    readme = repo / "README.md"
    try:
        readme.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    objective, _ = _sparse_repo_signals(repo)
    assert objective != "Leaked Secret Title"
    assert objective == ""


def test_sparse_scan_bounded_readme_scan(tmp_path: Path) -> None:
    """Huge README returns the first heading without scanning the entire file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    lines = ["# Early Heading\n", *("padding\n" for _ in range(10_000))]
    (repo / "README.md").write_text("".join(lines), encoding="utf-8")

    objective, _ = _sparse_repo_signals(repo)
    assert objective == "Early Heading"


def test_sparse_scan_skips_oversized_manifest(tmp_path: Path) -> None:
    """Oversized pyproject.toml is skipped without raising."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_bytes(b'[project]\nname = "' + b"x" * 2_000_000 + b'"\n')

    objective, _ = _sparse_repo_signals(repo)
    assert objective == ""


def test_sparse_scan_redacts_secret_in_readme(tmp_path: Path, invoke_main: Any) -> None:
    """README content passes through redact() before persisting."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# sk-proj-abcdefghijklmnopqrstuvwxyz123456\n",
        encoding="utf-8",
    )

    res = invoke_main(
        ["--repo", str(repo), "--format", "json", "init", "--draft", "git", "--no-git"]
    )
    assert res.exit_code == 0

    res_load = invoke_main(["--repo", str(repo), "--format", "json", "load"])
    payload = json.loads(res_load.stdout)
    assert "sk-proj-" not in payload["objective"]
    assert "[REDACTED]" in payload["objective"]
