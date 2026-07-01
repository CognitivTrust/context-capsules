import json
from typing import Any

from capsule.exit_codes import ExitCode


def build_patch(events: list[dict[str, Any]], version: str = "capsule-patch/v0") -> str:
    return f"""Some text
```capsule-patch
{json.dumps({"version": version, "events": events})}
```
More text
"""


def test_th6_context_apply_roundtrip(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-H6: context->apply round-trip via stdin lands events."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])

    patch_text = build_patch([{"id": "p1", "t": "progress", "note": "step 1"}])

    res_apply = invoke_cli(["--repo", str(tmp_path), "--format", "json", "apply"], input=patch_text)

    assert res_apply.exit_code == 0
    payload = json.loads(res_apply.stdout)
    assert payload["applied"] == ["p1"]
    assert payload["by"] == "web"

    # Verify in log
    res_log = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    log = json.loads(res_log.stdout)
    assert log[-1]["id"] == "p1"
    assert log[-1]["by"] == "web"


def test_te1_empty_patch(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-E1: empty patch events -> exit 0, no-op."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])
    patch_text = build_patch([])
    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "apply"], input=patch_text)
    assert res.exit_code == 0
    assert json.loads(res.stdout)["applied"] == []


def test_te2_idempotent_reapply(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-E2: idempotent re-apply."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])
    patch_text = build_patch([{"id": "p1", "t": "progress", "note": "step 1"}])

    invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text)
    res2 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "apply"], input=patch_text)

    assert res2.exit_code == 0
    payload = json.loads(res2.stdout)
    assert payload["applied"] == []
    assert payload["skipped"] == ["p1"]


def test_apply_dry_run_reports_without_writing(
    invoke_cli: Any, tmp_path: Any, monkeypatch: Any
) -> None:
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])
    patch_text = build_patch(
        [
            {"id": "p1", "t": "progress", "note": "step 1"},
            {"id": "p2", "t": "progress", "note": "step 2"},
        ]
    )

    res = invoke_cli(
        ["--repo", str(tmp_path), "--format", "json", "apply", "--dry-run"],
        input=patch_text,
    )

    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["dry_run"] is True
    assert payload["applied"] == ["p1", "p2"]
    assert payload["skipped"] == []

    res_log = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    assert json.loads(res_log.stdout) == []


def test_te5_batch_internal_linkage(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-E5: batch internal linkage."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])

    # Valid: question then resolution
    patch_text = build_patch(
        [
            {"id": "q1", "t": "question", "q": "what?"},
            {"id": "r1", "t": "resolution", "closes": "q1", "answer": "that"},
        ]
    )
    res = invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text)
    assert res.exit_code == 0

    # Invalid: resolution before question
    patch_text2 = build_patch(
        [
            {"id": "r2", "t": "resolution", "closes": "q2", "answer": "that"},
            {"id": "q2", "t": "question", "q": "what?"},
        ]
    )
    res2 = invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text2)
    assert res2.exit_code == ExitCode.SCHEMA


def test_te6_id_collision(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-E6: id collision with different content -> exit 4."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])

    patch_text1 = build_patch([{"id": "p1", "t": "progress", "note": "step 1"}])
    invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text1)

    patch_text2 = build_patch([{"id": "p1", "t": "progress", "note": "step 2"}])
    res = invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text2)
    assert res.exit_code == ExitCode.SCHEMA


def test_tf5_patch_rejection_matrix(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-F5: patch rejection matrix."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])

    cases = [
        "no fence at all",
        "```capsule-patch\n{unterminated",
        "```capsule-patch\nnot-json\n```",
        "```capsule-patch\n[]\n```",  # not object
        '```capsule-patch\n{"events":[]}\n```',  # missing version
        build_patch([], version="capsule-patch/v1"),  # unsupported major
        build_patch([{"t": "progress", "note": "n"}]),  # missing id
        build_patch([{"id": "1", "t": "bogus"}]),  # bad t
        build_patch([{"id": "1", "t": "progress"}]),  # missing note
    ]

    for case in cases:
        res = invoke_cli(["--repo", str(tmp_path), "apply"], input=case)
        assert res.exit_code == ExitCode.SCHEMA
        assert "capsule: error:" in res.stderr

    # Tolerated minor
    res_minor = invoke_cli(
        ["--repo", str(tmp_path), "apply"], input=build_patch([], version="capsule-patch/v0.9")
    )
    assert res_minor.exit_code == 0


def test_tf6_all_or_nothing(invoke_cli: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """T-F6: all-or-nothing (one bad event -> nothing appended)."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])

    patch_text = build_patch(
        [
            {"id": "p1", "t": "progress", "note": "step 1"},
            {"id": "p2", "t": "progress"},  # missing note
        ]
    )
    res = invoke_cli(["--repo", str(tmp_path), "apply"], input=patch_text)
    assert res.exit_code == ExitCode.SCHEMA

    # Assert log is empty
    res_log = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    assert len(json.loads(res_log.stdout)) == 0  # no events since draft none
