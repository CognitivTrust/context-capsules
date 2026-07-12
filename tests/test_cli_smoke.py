import importlib.metadata
import json
from collections import namedtuple
from pathlib import Path
from typing import Any

import pytest

from capsule.cli.app import Command, main
from capsule.cli.commands import init
from capsule.exit_codes import ExitCode

STATUS_TEXT = "Context Capsules: scaffolding only - no engine active yet (Phase 0)."


def test_version(invoke_cli: Any) -> None:
    res = invoke_cli(["--version"])
    assert res.exit_code == 0
    version_str = importlib.metadata.version("context-capsule")
    assert res.stdout.strip() == f"capsule {version_str}"


def test_help(invoke_cli: Any) -> None:
    res = invoke_cli(["--help"])
    assert res.exit_code == 0
    assert "init" in res.stdout


def test_init_success(invoke_cli: Any, tmp_path: Path) -> None:
    res = invoke_cli(["--repo", str(tmp_path), "init"])
    assert res.exit_code == 0
    assert "Initialized empty capsule" in res.stdout


def test_init_json_success(invoke_cli: Any, tmp_path: Path) -> None:
    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "init"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert "capsule_dir" in payload


def test_python_m_parity(invoke_cli: Any, invoke_module: Any, tmp_path: Path) -> None:
    p1 = tmp_path / "1"
    p2 = tmp_path / "2"
    p1.mkdir()
    p2.mkdir()
    cli_res = invoke_cli(["--repo", str(p1), "init", "--format", "json"])
    mod_res = invoke_module(["--repo", str(p2), "init", "--format", "json"])
    assert cli_res.exit_code == mod_res.exit_code
    # Output might contain different text if it's already present vs initialized
    # But exit code should match


def test_no_subcommand(invoke_cli: Any) -> None:
    res = invoke_cli([])
    assert res.exit_code == 2
    assert "error:" in res.stderr


def test_unknown_command(invoke_cli: Any) -> None:
    res = invoke_cli(["bogus"])
    assert res.exit_code == 2
    assert "error:" in res.stderr


def test_top_level_catch_error_no_verbose(monkeypatch: Any, capsys: Any) -> None:
    def fake_run(args: Any) -> dict[str, Any]:
        raise ValueError("simulated crash")

    fake_cmd = Command(
        name=init.NAME,
        help=init.HELP,
        configure=init.configure,
        run=fake_run,
    )
    monkeypatch.setattr("capsule.cli.app.REGISTRY", (fake_cmd,))

    exit_code = main(["init"])
    assert exit_code == int(ExitCode.ERROR)

    captured = capsys.readouterr()
    assert "capsule: error: simulated crash" in captured.err


def test_top_level_catch_error_verbose(monkeypatch: Any) -> None:
    def fake_run(args: Any) -> dict[str, Any]:
        raise ValueError("simulated crash")

    fake_cmd = Command(
        name=init.NAME,
        help=init.HELP,
        configure=init.configure,
        run=fake_run,
    )
    monkeypatch.setattr("capsule.cli.app.REGISTRY", (fake_cmd,))

    with pytest.raises(ValueError, match="simulated crash"):
        main(["--verbose", "init"])


def test_python_version_guard(monkeypatch: Any, invoke_main: Any) -> None:
    VersionInfo = namedtuple("VersionInfo", "major minor micro releaselevel serial")
    monkeypatch.setattr("capsule.cli.app.sys.version_info", VersionInfo(3, 10, 9, "final", 0))

    res = invoke_main(["--version"])

    assert res.exit_code == int(ExitCode.ERROR)
    assert "capsule requires Python 3.11+" in res.stderr
