from __future__ import annotations

import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


def test_sdist_hygiene(tmp_path: Path) -> None:
    if importlib.util.find_spec("build") is None:
        pytest.skip("build package is not importable")

    repo = Path(__file__).resolve().parent.parent
    outdir = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(outdir)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    archives = sorted(outdir.glob("*.tar.gz"))
    assert len(archives) == 1

    with tarfile.open(archives[0], "r:gz") as handle:
        members = [member.name for member in handle.getmembers()]

    stripped = [_strip_sdist_root(member) for member in members]
    assert "README.md" in stripped
    assert "PKG-INFO" in stripped
    assert all("__pycache__" not in member.split("/") for member in stripped)
    assert all(not member.endswith(".pyc") for member in stripped)


def _strip_sdist_root(member: str) -> str:
    parts = member.split("/", 1)
    if len(parts) == 1:
        return parts[0]
    return parts[1]
