from capsule.exit_codes import ExitCode


def test_exit_code_table() -> None:
    expected_values = {
        "OK": 0,
        "ERROR": 1,
        "USAGE": 2,
        "NO_CAPSULE": 3,
        "SCHEMA": 4,
        "LOCK_TIMEOUT": 5,
        "CORRUPT_LOG": 6,
        "EVIDENCE_UNREADABLE": 7,
    }

    # 8 members total
    assert len(ExitCode) == 8

    # Check value uniqueness (IntEnum guarantees this if @unique is used, but we can double check)
    assert len({e.value for e in ExitCode}) == 8

    # Names and values match expected
    for name, value in expected_values.items():
        assert ExitCode[name].value == value
        assert int(ExitCode[name]) == value
