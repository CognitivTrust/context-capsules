import json
from typing import Any

from capsule.exit_codes import ExitCode


def test_th1_grammar_parse_repeated_flags(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H1: required/optional/repeated flags parse. Repeated flags accumulate in order."""
    invoke_cli(["--repo", str(tmp_path), "init"])
    res = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "--format",
            "json",
            "record",
            "intent",
            "--objective",
            "obj",
            "--current-understanding",
            "u1",
            "--current-understanding",
            "u2",
            "--constraint",
            "c1",
            "--constraint",
            "c2",
            "--invariant",
            "i1",
            "--invariant",
            "i2",
            "--acceptance",
            "a1",
            "--acceptance",
            "a2",
            "--by",
            "test-user",
        ]
    )
    assert res.exit_code == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["objective"] == "obj"
    assert payload["current_understanding"] == ["u1", "u2"]
    assert payload["constraints"] == ["c1", "c2"]
    assert payload["invariants"] == ["i1", "i2"]
    assert payload["acceptance"] == ["a1", "a2"]
    assert payload["by"] == "test-user"


def test_th1_grammar_parse_q_alias(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H1: -q aliases --question."""
    invoke_cli(["--repo", str(tmp_path), "init"])
    res = invoke_cli(
        ["--repo", str(tmp_path), "--format", "json", "record", "question", "-q", "what?"]
    )
    assert res.exit_code == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["q"] == "what?"


def test_tf1_missing_required_flag(invoke_cli: Any) -> None:
    """T-F1: missing required flag -> argparse -> exit 2."""
    res = invoke_cli(["record", "intent"])
    assert res.exit_code == ExitCode.USAGE
    assert "the following arguments are required: --objective" in res.stderr

    res_q = invoke_cli(["record", "question"])
    assert res_q.exit_code == ExitCode.USAGE
    assert "the following arguments are required: --question/-q" in res_q.stderr


def test_th1_global_flags_after_two_level_command(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H1: --repo/--format/--verbose work after a two-level command
    (`record <kind>`, `task <start|end>`), not just before the top-level
    command or between it and the first subcommand. README promises these
    flags work "on every command"."""
    invoke_cli(["init", "--repo", str(tmp_path)])

    after_kind = invoke_cli(
        [
            "record",
            "decision",
            "--decision",
            "d",
            "--rationale",
            "r",
            "--repo",
            str(tmp_path),
            "--format",
            "json",
        ]
    )
    assert after_kind.exit_code == 0, after_kind.stderr
    assert json.loads(after_kind.stdout)["decision"] == "d"

    after_task_subcommand = invoke_cli(
        [
            "task",
            "start",
            "--task-id",
            "t1",
            "--objective",
            "obj",
            "--repo",
            str(tmp_path),
            "--format",
            "json",
        ]
    )
    assert after_task_subcommand.exit_code == 0, after_task_subcommand.stderr
    assert json.loads(after_task_subcommand.stdout)["task_id"] == "t1"

    after_task_end = invoke_cli(
        [
            "task",
            "end",
            "--task-id",
            "t1",
            "--outcome",
            "completed",
            "--repo",
            str(tmp_path),
        ]
    )
    assert after_task_end.exit_code == 0, after_task_end.stderr


def test_tf3_unknown_subcommand(invoke_cli: Any) -> None:
    """T-F3: unknown/deferred subcommand -> exit 2."""
    for sub in ["status", "diff", "revert", "stats", "connect", "mcp", "garbage"]:
        res = invoke_cli([sub])
        assert res.exit_code == ExitCode.USAGE
        assert "invalid choice" in res.stderr
