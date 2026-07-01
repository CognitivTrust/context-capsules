import json
import os
from typing import Any
from unittest.mock import patch

from capsule.cli.edge.drafter import IntentDraft


def test_tl1_stubbed_drafter(invoke_main: Any, tmp_path: Any) -> None:
    """T-L1, T-L4: stubbed Drafter exercises edge path deterministically."""

    def fake_select_drafter(*args: Any, **kwargs: Any) -> Any:
        class FakeDrafter:
            def draft(self, commits: Any, repo: Any) -> IntentDraft:
                return IntentDraft(
                    objective="llm-obj",
                    current_understanding=("llm-u1",),
                    constraints=(),
                    source="llm:test-model",
                )

        return FakeDrafter(), None

    with patch("capsule.cli.commands.init.select_drafter", fake_select_drafter):
        res = invoke_main(["--repo", str(tmp_path), "--format", "json", "init", "--draft", "llm"])

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["draft_source"] == "llm:test-model"

    res_load = invoke_main(["--repo", str(tmp_path), "--format", "json", "load"])
    load_payload = json.loads(res_load.stdout)
    assert load_payload["objective"] == "llm-obj"
    assert "llm:test-model" in load_payload["current_understanding"][0]


def test_tl2_no_key_fallback(invoke_main: Any, tmp_path: Any) -> None:
    """T-L2: no-key fallback to git-heuristic + stderr notice."""
    # Ensure env is clear
    env = os.environ.copy()
    env.pop("CAPSULE_LLM_API_KEY", None)

    with patch("capsule.cli.edge.drafter.read_api_key", return_value=None):
        res = invoke_main(["--repo", str(tmp_path), "--format", "json", "init", "--draft", "llm"])

    assert res.exit_code == 0
    assert "fell back to git heuristic" in res.stderr
    payload = json.loads(res.stdout)
    assert payload["draft_source"] == "git-heuristic"


def test_tl3_secret_hygiene(invoke_cli: Any, tmp_path: Any) -> None:
    """T-L3: secret hygiene, key not in log/render."""
    env = os.environ.copy()
    env["CAPSULE_LLM_API_KEY"] = "sk-super-secret-key"

    def fake_urllib_request(*args: Any, **kwargs: Any) -> Any:
        class FakeResponse:
            def read(self) -> bytes:
                return (
                    b'{"choices":[{"message":{"content":"{\\"objective\\":\\"secret-test\\"}"}}]}'
                )

        return FakeResponse()

    # Stub git to avoid needing real repo
    with patch("capsule.cli.edge.git.read_commits", return_value=[]):
        with patch("urllib.request.urlopen", fake_urllib_request):
            with patch.dict("os.environ", env):
                invoke_cli(["--repo", str(tmp_path), "init", "--draft", "llm"])

    log_text = (tmp_path / ".capsule" / "log.jsonl").read_text(encoding="utf-8")
    assert "sk-super-secret-key" not in log_text

    render_text = (tmp_path / ".capsule" / "capsule.md").read_text(encoding="utf-8")
    assert "sk-super-secret-key" not in render_text


def test_tl4_redaction() -> None:
    """T-L4: redaction."""
    from capsule.cli.edge.drafter import redact

    assert redact("Bearer sk-abc123def456") == "Bearer [REDACTED]"
    assert redact("key: sk-proj-1234567890abcdef") == "key: [REDACTED]"
