import json
from typing import Any

from capsule.exit_codes import ExitCode


def test_th2_record_mapping(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H2: each record <type> invokes mapped engine call and returns it."""
    invoke_cli(["--repo", str(tmp_path), "init"])

    # decision
    res = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "--format",
            "json",
            "record",
            "decision",
            "--decision",
            "d1",
            "--rationale",
            "r1",
            "--evidence",
            "url:https://example.com",
        ]
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["t"] == "decision"
    assert payload["decision"] == "d1"
    assert payload["evidence"][0] == {"kind": "url", "ref": "https://example.com"}
    assert payload["verified"] is True

    # resolution
    qid = invoke_cli(
        ["--repo", str(tmp_path), "--format", "json", "record", "question", "-q", "q1"]
    ).stdout.strip()
    qid = json.loads(qid)["id"]

    res2 = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "--format",
            "json",
            "record",
            "resolution",
            "--closes",
            qid,
            "--answer",
            "a1",
        ]
    )
    assert res2.exit_code == 0
    payload2 = json.loads(res2.stdout)
    assert payload2["t"] == "resolution"
    assert payload2["answer"] == "a1"
    assert payload2["closes"] == qid

    # progress
    res3 = invoke_cli(
        ["--repo", str(tmp_path), "--format", "json", "record", "progress", "--note", "p1"]
    )
    assert res3.exit_code == 0
    payload3 = json.loads(res3.stdout)
    assert payload3["t"] == "progress"
    assert payload3["note"] == "p1"
    assert "verified" not in payload3 or payload3["verified"] is None

    # Check that they appear in log
    log_res = invoke_cli(["--repo", str(tmp_path), "log", "--format", "json"])
    log_payload = json.loads(log_res.stdout)
    types = [e["t"] for e in log_payload]
    assert types == ["intent", "decision", "question", "resolution", "progress"]


def test_th4_evidence_parse(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H4: evidence parse: first-colon split, URL colons preserved."""
    invoke_cli(["--repo", str(tmp_path), "init"])
    res = invoke_cli(
        [
            "--repo",
            str(tmp_path),
            "--format",
            "json",
            "record",
            "progress",
            "--note",
            "p1",
            "--evidence",
            "file:src/app.py",
            "--evidence",
            "commit:abcdef",
            "--evidence",
            "test:tests/test_cli.py",
            "--evidence",
            "url:https://example.com:8080/foo:bar",
        ]
    )
    assert res.exit_code == 0, res.stderr
    payload = json.loads(res.stdout)
    evs = payload["evidence"]
    assert evs[0] == {"kind": "file", "ref": "src/app.py"}
    assert evs[1] == {"kind": "commit", "ref": "abcdef"}
    assert evs[2] == {"kind": "test", "ref": "tests/test_cli.py"}
    assert evs[3] == {"kind": "url", "ref": "https://example.com:8080/foo:bar"}


def test_tf2_malformed_evidence(invoke_cli: Any, tmp_path: Any) -> None:
    """T-F2: malformed evidence / unknown kind -> exit 2 / exit 4."""
    invoke_cli(["--repo", str(tmp_path), "init"])

    # no colon
    res1 = invoke_cli(
        ["--repo", str(tmp_path), "record", "progress", "--note", "n", "--evidence", "file"]
    )
    assert res1.exit_code == ExitCode.USAGE
    assert "evidence must be KIND:REF" in res1.stderr

    # empty kind
    res2 = invoke_cli(
        ["--repo", str(tmp_path), "record", "progress", "--note", "n", "--evidence", ":file.py"]
    )
    assert res2.exit_code == ExitCode.USAGE

    # empty ref
    res3 = invoke_cli(
        ["--repo", str(tmp_path), "record", "progress", "--note", "n", "--evidence", "file:"]
    )
    assert res3.exit_code == ExitCode.USAGE

    # unknown kind (T-F2) -> SchemaError
    res4 = invoke_cli(
        ["--repo", str(tmp_path), "record", "progress", "--note", "n", "--evidence", "foo:bar"]
    )
    assert res4.exit_code == ExitCode.SCHEMA
    assert "capsule: error:" in res4.stderr


def test_tf4_no_capsule_record(invoke_cli: Any, tmp_path: Any) -> None:
    """T-F4: NoCapsule for record -> exit 3."""
    res = invoke_cli(["--repo", str(tmp_path), "record", "progress", "--note", "n"])
    assert res.exit_code == ExitCode.NO_CAPSULE
    assert "capsule: error:" in res.stderr
