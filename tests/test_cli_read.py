import json
from typing import Any

from capsule.exit_codes import ExitCode


def test_th3_read_commands(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H3: load text/json, show text/json, log text/json."""
    invoke_cli(["--repo", str(tmp_path), "init"])
    invoke_cli(
        ["--repo", str(tmp_path), "record", "decision", "--decision", "D1", "--rationale", "R1"]
    )

    # load
    res_load_text = invoke_cli(["--repo", str(tmp_path), "load"])
    assert res_load_text.exit_code == 0
    assert "D1" in res_load_text.stdout

    res_load_json = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    assert res_load_json.exit_code == 0
    payload = json.loads(res_load_json.stdout)
    assert payload["decisions"][0]["decision"] == "D1"
    assert payload["objective"] is None
    assert payload["open_tasks"] == []
    assert payload["event_count"] == 1

    # show
    res_show_text = invoke_cli(["--repo", str(tmp_path), "show"])
    assert res_show_text.exit_code == 0
    assert "## Decisions" in res_show_text.stdout
    assert "D1" in res_show_text.stdout

    res_show_json = invoke_cli(["--repo", str(tmp_path), "--format", "json", "show"])
    assert res_show_json.exit_code == 0
    payload_show = json.loads(res_show_json.stdout)
    assert "markdown" in payload_show
    assert "## Decisions" in payload_show["markdown"]

    # log
    res_log_text = invoke_cli(["--repo", str(tmp_path), "log"])
    assert res_log_text.exit_code == 0
    assert "decision" in res_log_text.stdout
    assert "D1" in res_log_text.stdout

    res_log_json = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    assert res_log_json.exit_code == 0
    payload_log = json.loads(res_log_json.stdout)
    assert len(payload_log) == 1
    assert payload_log[0]["t"] == "decision"
    assert payload_log[0]["decision"] == "D1"


def test_te3_large_empty_log(invoke_cli: Any, tmp_path: Any) -> None:
    """T-E3: large/empty log. log --limit."""
    invoke_cli(["--repo", str(tmp_path), "init"])

    # empty log
    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == []

    # large log
    for i in range(10):
        invoke_cli(["--repo", str(tmp_path), "record", "progress", "--note", f"n{i}"])

    res2 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    assert res2.exit_code == 0
    payload = json.loads(res2.stdout)
    assert len(payload) == 10

    # limit 0
    res3 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log", "--limit", "0"])
    assert res3.exit_code == 0
    assert json.loads(res3.stdout) == []

    # limit > len
    res4 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log", "--limit", "15"])
    assert res4.exit_code == 0
    assert len(json.loads(res4.stdout)) == 10

    # limit normal
    res5 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log", "--limit", "3"])
    assert res5.exit_code == 0
    payload5 = json.loads(res5.stdout)
    assert len(payload5) == 3
    assert payload5[-1]["note"] == "n9"

    # negative limit
    res6 = invoke_cli(["--repo", str(tmp_path), "log", "--limit", "-1"])
    assert res6.exit_code == ExitCode.USAGE


def test_tf4_read_no_capsule(invoke_cli: Any, tmp_path: Any) -> None:
    """T-F4: load/show/log -> exit 3 on no capsule."""
    for cmd in ["load", "show", "log"]:
        res = invoke_cli(["--repo", str(tmp_path), cmd])
        assert res.exit_code == ExitCode.NO_CAPSULE


def test_ts2_golden_read(invoke_cli: Any, tmp_path: Any) -> None:
    """T-S2, T-S3: golden fold/render shapes and field-name fidelity."""
    invoke_cli(["--repo", str(tmp_path), "init"])
    invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "intent",
            "--objective",
            "golden_obj",
            "--current-understanding",
            "u1",
            "--constraint",
            "c1",
            "--invariant",
            "i1",
            "--acceptance",
            "a1",
        ]
    )
    invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "record",
            "decision",
            "--decision",
            "d1",
            "--rationale",
            "r1",
            "--evidence",
            "file:x.py",
        ]
    )
    qid = json.loads(
        invoke_cli(
            ["--repo", str(tmp_path), "--format", "json", "record", "question", "-q", "q1"]
        ).stdout
    )["id"]
    invoke_cli(
        ["--repo", str(tmp_path), "record", "resolution", "--closes", qid, "--answer", "ans1"]
    )
    invoke_cli(["--repo", str(tmp_path), "record", "progress", "--note", "prog1"])

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    payload = json.loads(res.stdout)
    assert payload["objective"] == "golden_obj"
    assert payload["current_understanding"] == ["u1"]
    assert payload["constraints"] == ["c1"]
    assert payload["invariants"] == ["i1"]
    assert payload["acceptance"] == ["a1"]

    assert len(payload["decisions"]) == 1
    d = payload["decisions"][0]
    assert "id" in d and "at" in d and "by" in d
    assert d["decision"] == "d1"
    assert d["rationale"] == "r1"
    assert d["evidence"] == [{"kind": "file", "ref": "x.py"}]
    assert d["verified"] is False

    assert len(payload["open_questions"]) == 0
    assert payload["open_tasks"] == []
    assert len(payload["resolved_questions"]) == 1
    r = payload["resolved_questions"][0]
    assert r["q"] == "q1"
    assert r["answer"] == "ans1"
    assert "resolved_by" in r

    assert len(payload["progress"]) == 1
    p = payload["progress"][0]
    assert p["note"] == "prog1"
    assert p["verified"] is None

    assert payload["event_count"] == 5

    # Log shape verification
    res_log = invoke_cli(["--repo", str(tmp_path), "--format", "json", "log"])
    payload_log = json.loads(res_log.stdout)
    assert len(payload_log) == 5
    for ev in payload_log:
        assert "t" in ev and "id" in ev and "at" in ev and "by" in ev
