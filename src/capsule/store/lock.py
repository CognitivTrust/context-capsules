"""Cross-platform advisory capsule lock."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import portalocker

from capsule.engine.errors import CapsuleError, LockTimeout

LOCK_TIMEOUT_SECONDS: float = 5.0
LOCK_POLL_SECONDS: float = 0.05


@contextmanager
def capsule_lock(
    lock_path: Path,
    *,
    timeout: float = LOCK_TIMEOUT_SECONDS,
    poll: float = LOCK_POLL_SECONDS,
) -> Iterator[None]:
    deadline = time.monotonic() + max(timeout, 0.0)
    try:
        with lock_path.open("a", encoding="utf-8", newline="") as handle:
            while True:
                try:
                    portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
                    break
                except portalocker.exceptions.LockException as exc:
                    if time.monotonic() >= deadline:
                        raise LockTimeout(
                            f"timed out acquiring capsule lock at {lock_path}"
                        ) from exc
                    time.sleep(max(poll, 0.0))
            try:
                yield
            finally:
                portalocker.unlock(handle)
    except OSError as exc:
        raise CapsuleError(f"lock operation failed at {lock_path}: {exc}") from exc
