import io
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import NamedTuple

import pytest


class CLiResult(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str


@pytest.fixture
def invoke_main(capsys: pytest.CaptureFixture[str]) -> Callable[..., CLiResult]:
    """Invokes the capsule CLI in-process via app.main(), allowing mocks."""
    from capsule.cli.app import main

    def _invoke(
        args: Sequence[str], cwd: str | os.PathLike[str] | None = None, input: str | None = None
    ) -> CLiResult:
        old_cwd = os.getcwd()
        if cwd:
            os.chdir(cwd)
        old_stdin = sys.stdin
        if input is not None:
            sys.stdin = io.StringIO(input)
        try:
            exit_code = main(list(args))
            captured = capsys.readouterr()
            return CLiResult(exit_code, captured.out, captured.err)
        finally:
            if cwd:
                os.chdir(old_cwd)
            sys.stdin = old_stdin

    return _invoke


@pytest.fixture
def invoke_cli() -> Callable[..., CLiResult]:
    """Invokes the console script 'capsule'."""
    capsule_bin = shutil.which("capsule")
    if not capsule_bin:
        pytest.fail("capsule console script not found. Is the package installed?")

    def _invoke(
        args: Sequence[str], cwd: str | os.PathLike[str] | None = None, input: str | None = None
    ) -> CLiResult:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [capsule_bin, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=cwd,
            input=input,
            check=False,
        )
        return CLiResult(result.returncode, result.stdout, result.stderr)

    return _invoke


@pytest.fixture
def invoke_module() -> Callable[..., CLiResult]:
    """Invokes 'python -m capsule'."""

    def _invoke(args: Sequence[str], cwd: str | os.PathLike[str] | None = None) -> CLiResult:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "capsule", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=cwd,
            check=False,
        )
        return CLiResult(result.returncode, result.stdout, result.stderr)

    return _invoke
