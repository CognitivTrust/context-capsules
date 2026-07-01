import json

import pytest

from capsule.cli.formatting import format_output


def test_format_output_text_with_message() -> None:
    payload = {"message": "Hello world", "other": "ignored"}
    assert format_output(payload, "text") == "Hello world"


def test_format_output_text_without_message() -> None:
    payload = {"z": 1, "a": 2, "c": 3}
    expected = "a: 2\nc: 3\nz: 1"
    assert format_output(payload, "text") == expected


def test_format_output_json_roundtrip() -> None:
    payload = {"z": 1, "message": "Hello", "a": [1, 2]}
    json_str = format_output(payload, "json")

    # No trailing newline
    assert not json_str.endswith("\n")

    parsed = json.loads(json_str)
    assert parsed == payload


def test_format_output_bad_fmt() -> None:
    payload = {"message": "Hello"}
    with pytest.raises(ValueError):
        format_output(payload, "zzz")
