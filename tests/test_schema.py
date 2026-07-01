import json
import random
import string
from pathlib import Path
from typing import Any

import pytest

from capsule.engine.errors import SchemaError
from capsule.engine.events import ByObject, Event, Evidence
from capsule.engine.schema import from_obj


def test_round_trip_identity() -> None:
    # 12. Round-trip identity.
    canonical_path = Path(__file__).parent / "fixtures" / "canonical.jsonl"
    with open(canonical_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    for line in lines:
        obj = json.loads(line)
        event = from_obj(obj)
        re_serialized = event.to_jsonl()
        # The re_serialized string should exactly match the canonical line
        assert re_serialized == line
        # And from_obj of the reserialized should match the original event
        assert from_obj(json.loads(re_serialized)) == event


def random_string(min_len: int = 1, max_len: int = 20) -> str:
    # ASCII letters to avoid JSON surrogate surrogate issues for simplicity
    length = random.randint(min_len, max_len)
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


def generate_random_event() -> Event:
    t = random.choice(
        ["intent", "decision", "question", "resolution", "progress", "task_start", "task_end"]
    )
    kwargs: dict[str, Any] = {
        "t": t,
        "id": random_string(),
        "at": random_string(),
        "by": random.choice(
            [
                None,
                random_string(),
                ByObject(
                    principal=random_string(),
                    subagent=random.choice([None, random_string()]),
                    model=random.choice([None, random_string()]),
                    session=random.choice([None, random_string()]),
                    task=random.choice([None, random_string()]),
                ),
            ]
        ),
    }

    def rand_evidence_list() -> list[Evidence]:
        if random.random() < 0.5:
            return []
        res = []
        for _ in range(random.randint(1, 3)):
            res.append(
                Evidence(kind=random.choice(["file", "commit", "test", "url"]), ref=random_string())
            )
        return res

    if t == "intent":
        kwargs["objective"] = random_string()
        kwargs["current_understanding"] = tuple(
            random_string() for _ in range(random.randint(0, 2))
        )
        kwargs["constraints"] = tuple(random_string() for _ in range(random.randint(0, 2)))
        kwargs["invariants"] = tuple(random_string() for _ in range(random.randint(0, 2)))
        kwargs["acceptance"] = tuple(random_string() for _ in range(random.randint(0, 2)))
    elif t == "decision":
        kwargs["decision"] = random_string()
        kwargs["rationale"] = random_string()
        ev = rand_evidence_list()
        if ev:
            kwargs["evidence"] = tuple(ev)
            kwargs["verified"] = random.choice([True, False])
    elif t == "question":
        kwargs["q"] = random_string()
    elif t == "resolution":
        kwargs["closes"] = random_string()
        kwargs["answer"] = random_string()
    elif t == "progress":
        kwargs["note"] = random_string()
        ev = rand_evidence_list()
        if ev:
            kwargs["evidence"] = tuple(ev)
            kwargs["verified"] = random.choice([True, False])
    elif t == "task_start":
        kwargs["task_id"] = random_string()
        kwargs["objective"] = random_string()
        if random.random() < 0.5:
            kwargs["for_intent"] = random_string()
    elif t == "task_end":
        kwargs["closes_task"] = random_string()
        kwargs["outcome"] = random.choice(["completed", "abandoned", "superseded"])
        if random.random() < 0.5:
            kwargs["summary"] = random_string()

    return Event(**kwargs)


def test_property_round_trip() -> None:
    # 13. Property test. Randomly generated valid events round trip.
    random.seed(42)
    for _ in range(100):
        event = generate_random_event()
        line = event.to_jsonl()
        obj = json.loads(line)
        new_event = from_obj(obj)
        assert new_event == event


def test_forward_compat_preservation() -> None:
    # 14. Forward-compat preservation.
    obj: dict[str, Any] = {
        "t": "decision",
        "id": "e1",
        "at": "2026-06-05T12:30:00Z",
        "by": "test",
        "decision": "D",
        "rationale": "R",
        "evidence": [{"kind": "file", "ref": "x.py", "unknown_ref_key": "val"}],
        "verified": True,
        "unknown_top_level": 42,
    }
    event = from_obj(obj)
    assert event.extra == {"unknown_top_level": 42}
    assert event.evidence[0].extra == {"unknown_ref_key": "val"}

    # to_jsonl should re-emit them
    re_obj = json.loads(event.to_jsonl())
    assert re_obj["unknown_top_level"] == 42
    assert re_obj["evidence"][0]["unknown_ref_key"] == "val"


def test_required_field_failure_paths() -> None:
    # 15. Required-field failure paths.
    base: dict[str, Any] = {"t": "intent", "id": "1", "at": "now", "objective": "obj"}

    # missing t
    with pytest.raises(SchemaError):
        bad1 = dict(base)
        del bad1["t"]
        from_obj(bad1)

    # missing id
    with pytest.raises(SchemaError):
        bad2 = dict(base)
        del bad2["id"]
        from_obj(bad2)

    # missing at
    with pytest.raises(SchemaError):
        bad3 = dict(base)
        del bad3["at"]
        from_obj(bad3)

    # missing objective on intent
    with pytest.raises(SchemaError):
        bad4 = dict(base)
        del bad4["objective"]
        from_obj(bad4)

    # decision
    base_dec: dict[str, Any] = {
        "t": "decision",
        "id": "1",
        "at": "now",
        "decision": "D",
        "rationale": "R",
    }
    with pytest.raises(SchemaError):
        bad_dec1 = dict(base_dec)
        del bad_dec1["decision"]
        from_obj(bad_dec1)

    with pytest.raises(SchemaError):
        bad_dec2 = dict(base_dec)
        del bad_dec2["rationale"]
        from_obj(bad_dec2)

    # question
    base_q: dict[str, Any] = {"t": "question", "id": "1", "at": "now", "q": "Q"}
    with pytest.raises(SchemaError):
        bad_q1 = dict(base_q)
        del bad_q1["q"]
        from_obj(bad_q1)

    # resolution
    base_res: dict[str, Any] = {
        "t": "resolution",
        "id": "1",
        "at": "now",
        "closes": "q1",
        "answer": "A",
    }
    with pytest.raises(SchemaError):
        bad_res1 = dict(base_res)
        del bad_res1["closes"]
        from_obj(bad_res1)

    with pytest.raises(SchemaError):
        bad_res2 = dict(base_res)
        del bad_res2["answer"]
        from_obj(bad_res2)

    # progress
    base_prog: dict[str, Any] = {"t": "progress", "id": "1", "at": "now", "note": "N"}
    with pytest.raises(SchemaError):
        bad_prog1 = dict(base_prog)
        del bad_prog1["note"]
        from_obj(bad_prog1)

    base_task_start: dict[str, Any] = {
        "t": "task_start",
        "id": "1",
        "at": "now",
        "task_id": "task-1",
        "objective": "Do work",
    }
    with pytest.raises(SchemaError):
        bad_task_start1 = dict(base_task_start)
        del bad_task_start1["task_id"]
        from_obj(bad_task_start1)

    with pytest.raises(SchemaError):
        bad_task_start2 = dict(base_task_start)
        del bad_task_start2["objective"]
        from_obj(bad_task_start2)

    base_task_end: dict[str, Any] = {
        "t": "task_end",
        "id": "1",
        "at": "now",
        "closes_task": "task-1",
        "outcome": "completed",
    }
    with pytest.raises(SchemaError):
        bad_task_end1 = dict(base_task_end)
        del bad_task_end1["closes_task"]
        from_obj(bad_task_end1)


def test_type_enum_failures() -> None:
    # 16. Type/enum failures.
    base: dict[str, Any] = {"t": "intent", "id": "1", "at": "now", "objective": "O"}

    # t not in enum
    with pytest.raises(SchemaError):
        bad1 = dict(base)
        bad1["t"] = "bogus"
        from_obj(bad1)

    # evidence.kind not in enum
    with pytest.raises(SchemaError):
        bad_dec1: dict[str, Any] = {
            "t": "decision",
            "id": "1",
            "at": "now",
            "decision": "D",
            "rationale": "R",
            "evidence": [{"kind": "bogus", "ref": "x"}],
            "verified": False,
        }
        from_obj(bad_dec1)

    # list field given non-list
    with pytest.raises(SchemaError):
        bad2 = dict(base)
        bad2["current_understanding"] = "not-a-list"
        from_obj(bad2)

    # list field containing non-string
    with pytest.raises(SchemaError):
        bad3 = dict(base)
        bad3["current_understanding"] = [123]
        from_obj(bad3)

    # scalar given non-string
    with pytest.raises(SchemaError):
        bad4 = dict(base)
        bad4["objective"] = 123
        from_obj(bad4)

    # verified non-bool
    with pytest.raises(SchemaError):
        bad_dec2: dict[str, Any] = {
            "t": "decision",
            "id": "1",
            "at": "now",
            "decision": "D",
            "rationale": "R",
            "evidence": [{"kind": "file", "ref": "x"}],
            "verified": "yes",
        }
        from_obj(bad_dec2)

    with pytest.raises(SchemaError):
        bad_task_end: dict[str, Any] = {
            "t": "task_end",
            "id": "1",
            "at": "now",
            "closes_task": "task-1",
            "outcome": "bogus",
        }
        from_obj(bad_task_end)


def test_disallowed_field_failures() -> None:
    # 17. Disallowed-field failures.

    # closes on non-resolution
    with pytest.raises(SchemaError):
        bad1: dict[str, Any] = {"t": "question", "id": "1", "at": "now", "q": "Q", "closes": "x"}
        from_obj(bad1)

    # evidence on intent
    with pytest.raises(SchemaError):
        bad2: dict[str, Any] = {
            "t": "intent",
            "id": "1",
            "at": "now",
            "objective": "O",
            "evidence": [{"kind": "file", "ref": "x"}],
        }
        from_obj(bad2)

    # verified without non-empty evidence
    with pytest.raises(SchemaError):
        bad3: dict[str, Any] = {
            "t": "decision",
            "id": "1",
            "at": "now",
            "decision": "D",
            "rationale": "R",
            "verified": True,
        }
        from_obj(bad3)

    # evidence present but empty -> verified must NOT be present
    with pytest.raises(SchemaError):
        bad4: dict[str, Any] = {
            "t": "decision",
            "id": "1",
            "at": "now",
            "decision": "D",
            "rationale": "R",
            "evidence": [],
            "verified": True,
        }
        from_obj(bad4)

    # evidence present -> verified must be present
    with pytest.raises(SchemaError):
        bad5: dict[str, Any] = {
            "t": "decision",
            "id": "1",
            "at": "now",
            "decision": "D",
            "rationale": "R",
            "evidence": [{"kind": "file", "ref": "x"}],
        }
        from_obj(bad5)

    # decision on intent
    with pytest.raises(SchemaError):
        bad6: dict[str, Any] = {
            "t": "intent",
            "id": "1",
            "at": "now",
            "objective": "O",
            "decision": "D",
        }
        from_obj(bad6)

    # closes_task on non-task_end
    with pytest.raises(SchemaError):
        bad7: dict[str, Any] = {
            "t": "progress",
            "id": "1",
            "at": "now",
            "note": "N",
            "closes_task": "task-1",
        }
        from_obj(bad7)
