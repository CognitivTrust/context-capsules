from typing import Any
from unittest.mock import patch


def test_tx2_clipboard_unavailable(invoke_main: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-X2: clipboard fallback when unavailable."""
    invoke_main(["--repo", str(tmp_path), "init", "--draft", "none"])

    # context
    with patch("capsule.cli.commands.context.copy_to_clipboard", return_value=False):
        res = invoke_main(["--repo", str(tmp_path), "context", "--clip"])
    assert res.exit_code == 0
    assert "clipboard unavailable" in res.stderr
    assert "```capsule-patch" in res.stdout  # printed to stdout

    # apply
    with patch("capsule.cli.commands.apply.read_from_clipboard", return_value=None):
        res_apply = invoke_main(
            ["--repo", str(tmp_path), "apply", "--clip"],
            input='```capsule-patch\n{"version":"capsule-patch/v0","events":[]}\n```',
        )
    assert res_apply.exit_code == 0
    assert "clipboard unavailable" in res_apply.stderr


def test_tx2_clipboard_available(invoke_main: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-X2: clipboard copy/paste successful."""
    invoke_main(["--repo", str(tmp_path), "init", "--draft", "none"])

    # context
    with patch("capsule.cli.commands.context.copy_to_clipboard", return_value=True):
        res = invoke_main(["--repo", str(tmp_path), "context", "--clip"])
    assert res.exit_code == 0
    assert "copied context block to clipboard" in res.stderr
    assert res.stdout == ""  # clean stdout

    # apply
    patch_text = (
        '```capsule-patch\n{"version":"capsule-patch/v0","events":'
        '[{"id":"c1", "t":"progress", "note":"clip"}]}\n```'
    )
    with patch("capsule.cli.commands.apply.read_from_clipboard", return_value=patch_text):
        res_apply = invoke_main(["--repo", str(tmp_path), "--format", "json", "apply", "--clip"])
    assert res_apply.exit_code == 0
    import json

    assert json.loads(res_apply.stdout)["applied"] == ["c1"]


def test_tx2_clipboard_tool_selection(monkeypatch: Any) -> None:
    """T-X2: OS tool selection mocked."""
    import platform

    from capsule.cli.edge.clipboard import _clipboard_copy_argv, _clipboard_paste_argv

    def mock_which(cmd: str) -> str | None:
        if cmd in ("pbcopy", "pbpaste"):
            return f"/usr/bin/{cmd}"
        return None

    monkeypatch.setattr("shutil.which", mock_which)

    with patch.object(platform, "system", return_value="Darwin"):
        assert _clipboard_copy_argv() == ["pbcopy"]
        assert _clipboard_paste_argv() == ["pbpaste"]
