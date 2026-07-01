from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from capsule.engine.engine import Engine
from capsule.engine.events import Evidence
from capsule.engine.verify import FileEvidenceVerifier, VerifierRegistry, default_registry


def test_default_engine_verifies_existing_file(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("print('ok')\n", encoding="utf-8")
    engine = Engine(tmp_path)
    engine.init()

    event = engine.record_decision(decision="D", rationale="R", evidence=[Evidence("file", "x.py")])

    assert event.verified is True
    log_path = tmp_path / ".capsule" / "log.jsonl"
    assert b'"verified":true' in log_path.read_bytes()


def test_verify_all_semantics(tmp_path: Path) -> None:
    registry = VerifierRegistry()

    assert registry.verify_all((Evidence("file", "x"),), tmp_path) is False
    assert (
        registry.verify_all((Evidence("file", "x"), Evidence("commit", "abc")), tmp_path) is False
    )


def test_file_verifier_rejects_traversal_without_statting_outside(
    tmp_path: Path, monkeypatch: Any
) -> None:
    verifier = FileEvidenceVerifier()

    def fail_exists(self: Path) -> bool:
        raise AssertionError(f"should not stat {self}")

    monkeypatch.setattr(Path, "exists", fail_exists)

    assert verifier.verify("../../etc/passwd", tmp_path) is False
    assert verifier.verify("/etc/passwd", tmp_path) is False
    assert verifier.verify("..\\..\\secret", tmp_path) is False


def test_commit_verifier_uses_local_git_and_caches(tmp_path: Path, monkeypatch: Any) -> None:
    _run_git(tmp_path, "init")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    _run_git(tmp_path, "add", "tracked.txt")
    _run_git(
        tmp_path,
        "-c",
        "user.name=Capsule Tests",
        "-c",
        "user.email=capsule@example.com",
        "commit",
        "-m",
        "seed",
    )
    commit_ref = _run_git(tmp_path, "rev-parse", "HEAD")
    registry = default_registry()
    original_run = subprocess.run
    calls = 0

    def counting_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr("capsule.engine.verify.subprocess.run", counting_run)

    verified = registry.verify_all(
        (Evidence("commit", commit_ref), Evidence("commit", commit_ref)),
        tmp_path,
    )

    assert verified is True
    assert calls == 1


def test_test_verifier_checks_path_existence_only(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_present():\n    assert True\n", encoding="utf-8"
    )
    registry = default_registry()

    verified = registry.verify_all(
        (Evidence("test", "tests/test_sample.py::test_missing_symbol"),),
        tmp_path,
    )

    assert verified is True


def test_url_verifier_is_syntax_only(tmp_path: Path) -> None:
    registry = default_registry()

    assert registry.verify_all((Evidence("url", "https://example.com/path"),), tmp_path) is True
    assert registry.verify_all((Evidence("url", "ftp://example.com"),), tmp_path) is False
    assert registry.verify_all((Evidence("url", "https:///missing-host"),), tmp_path) is False


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()
