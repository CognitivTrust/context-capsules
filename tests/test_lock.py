import multiprocessing
import time
from pathlib import Path
from typing import Any

import pytest

import capsule.store.lock as lock_module
from capsule.engine.errors import LockTimeout
from capsule.store.lock import capsule_lock


def _hold_lock(lock_path: Path, hold_time: float, event: Any) -> None:
    with capsule_lock(lock_path):
        event.set()
        time.sleep(hold_time)


def test_lock_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 26. Lock timeout (no infinite loop).
    lock_path = tmp_path / ".lock"

    # Patch the timeout so we don't wait 5 seconds in tests
    monkeypatch.setattr(lock_module, "LOCK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(lock_module, "LOCK_POLL_SECONDS", 0.01)

    event = multiprocessing.Event()
    # Start a background process that holds the lock for 2.0s
    p = multiprocessing.Process(target=_hold_lock, args=(lock_path, 2.0, event))
    p.start()

    # Wait for background process to actually acquire the lock
    event.wait(timeout=5.0)

    try:
        # This should time out
        with pytest.raises(LockTimeout):
            with capsule_lock(lock_path, timeout=0.1):
                pass
    finally:
        p.join()
