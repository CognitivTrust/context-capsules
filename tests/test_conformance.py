import json
from pathlib import Path
from typing import Any

import pytest

from capsule.engine.errors import SchemaError
from capsule.engine.schema import from_obj


def _canonical_fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "canonical.jsonl"


def _spec_path() -> Path:
    return Path(__file__).resolve().parent.parent / "SPEC.md"


def _extract_spec_canonical_log(spec_text: str) -> str:
    start_marker = "## Canonical Example Log\n\n```jsonl\n"
    end_marker = "\n```"
    start = spec_text.index(start_marker) + len(start_marker)
    end = spec_text.index(end_marker, start)
    return spec_text[start:end] + "\n"


def test_conformance_canonical_log() -> None:
    # Conformance: the canonical example log loads
    canonical_path = _canonical_fixture_path()
    with open(canonical_path, encoding="utf-8") as f:
        for line in f:
            from_obj(json.loads(line))


def test_conformance_canonical_fixture_matches_spec() -> None:
    # SPEC.md is not tracked in this repo (it is published separately), so
    # this check only runs when a local copy happens to be present.
    spec_path = _spec_path()
    if not spec_path.exists():
        pytest.skip(f"{spec_path} not present locally; skipping spec/fixture sync check")

    canonical_text = _canonical_fixture_path().read_text(encoding="utf-8")
    spec_text = spec_path.read_text(encoding="utf-8")

    assert canonical_text == _extract_spec_canonical_log(spec_text)


def test_conformance_malformed_catalogue() -> None:
    # Every entry in the malformed-input catalogue is rejected by from_obj
    base: dict[str, Any] = {"t": "intent", "id": "1", "at": "now", "objective": "O"}

    def assert_rejects(obj: dict[str, Any], reason: str = "") -> None:
        with pytest.raises(SchemaError):
            from_obj(obj)

    # Missing required fields
    for field in ["t", "id", "at"]:
        bad = base.copy()
        del bad[field]
        assert_rejects(bad)

    bad_intent = base.copy()
    del bad_intent["objective"]
    assert_rejects(bad_intent)

    base_dec: dict[str, Any] = {
        "t": "decision",
        "id": "1",
        "at": "now",
        "decision": "D",
        "rationale": "R",
    }
    bad_dec1 = base_dec.copy()
    del bad_dec1["decision"]
    assert_rejects(bad_dec1)
    bad_dec2 = base_dec.copy()
    del bad_dec2["rationale"]
    assert_rejects(bad_dec2)

    base_q: dict[str, Any] = {"t": "question", "id": "1", "at": "now", "q": "Q"}
    bad_q = base_q.copy()
    del bad_q["q"]
    assert_rejects(bad_q)

    base_res: dict[str, Any] = {
        "t": "resolution",
        "id": "1",
        "at": "now",
        "closes": "q1",
        "answer": "A",
    }
    bad_res1 = base_res.copy()
    del bad_res1["closes"]
    assert_rejects(bad_res1)
    bad_res2 = base_res.copy()
    del bad_res2["answer"]
    assert_rejects(bad_res2)

    base_prog: dict[str, Any] = {"t": "progress", "id": "1", "at": "now", "note": "N"}
    bad_prog = base_prog.copy()
    del bad_prog["note"]
    assert_rejects(bad_prog)

    base_task_start: dict[str, Any] = {
        "t": "task_start",
        "id": "1",
        "at": "now",
        "task_id": "task-1",
        "objective": "Wire CLI task lifecycle",
    }
    bad_task_start1 = base_task_start.copy()
    del bad_task_start1["task_id"]
    assert_rejects(bad_task_start1)
    bad_task_start2 = base_task_start.copy()
    del bad_task_start2["objective"]
    assert_rejects(bad_task_start2)

    base_task_end: dict[str, Any] = {
        "t": "task_end",
        "id": "1",
        "at": "now",
        "closes_task": "task-1",
        "outcome": "completed",
    }
    bad_task_end1 = base_task_end.copy()
    del bad_task_end1["closes_task"]
    assert_rejects(bad_task_end1)
    bad_task_end2 = base_task_end.copy()
    bad_task_end2["outcome"] = "bogus"
    assert_rejects(bad_task_end2)

    # Enums
    bad_enum = base.copy()
    bad_enum["t"] = "bogus"
    assert_rejects(bad_enum)
    bad_enum2 = base_dec.copy()
    bad_enum2["evidence"] = [{"kind": "bogus", "ref": "x"}]
    assert_rejects(bad_enum2)

    # Types
    bad_scalar = base.copy()
    bad_scalar["objective"] = 123
    assert_rejects(bad_scalar)
    bad_empty_str = base.copy()
    bad_empty_str["objective"] = ""
    assert_rejects(bad_empty_str)
    bad_list = base.copy()
    bad_list["constraints"] = "not-a-list"
    assert_rejects(bad_list)
    bad_list_elem = base.copy()
    bad_list_elem["constraints"] = [123]
    assert_rejects(bad_list_elem)

    bad_bool = base_dec.copy()
    bad_bool["evidence"] = [{"kind": "file", "ref": "x"}]
    bad_bool["verified"] = "yes"
    assert_rejects(bad_bool)

    # Disallowed
    bad_closes = base_q.copy()
    bad_closes["closes"] = "x"
    assert_rejects(bad_closes)
    bad_closes_task = base_prog.copy()
    bad_closes_task["closes_task"] = "task-1"
    assert_rejects(bad_closes_task)
    bad_ev = base.copy()
    bad_ev["evidence"] = [{"kind": "file", "ref": "x"}]
    assert_rejects(bad_ev)
    bad_ver = base_dec.copy()
    bad_ver["verified"] = True
    assert_rejects(bad_ver)

    bad_cross = base.copy()
    bad_cross["decision"] = "D"
    assert_rejects(bad_cross)
