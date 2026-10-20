import errno
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from capsule.engine.errors import CapsuleError, CorruptLogLine, SchemaError
from capsule.store import store as store_module
from capsule.store.paths import CapsulePaths
from capsule.store.store import Store


def test_store_create_layout(tmp_path: Path) -> None:
    # 2. `init` creates exactly the layout. (Testing store part)
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    assert not store.exists()

    store.create()
    assert store.exists()
    assert paths.capsule_dir.is_dir()
    assert paths.log.is_file()
    assert paths.log.stat().st_size == 0
    # .lock is created on first lock, capsule.md is written via atomic write


def test_mid_log_corruption(tmp_path: Path) -> None:
    # 20. Mid-log corruption.
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    with open(paths.log, "wb") as f:
        f.write(b'{"t":"intent","id":"1","at":"now","objective":"obj"}\n')
        f.write(b'{"t":"intent"  bad json \n')
        f.write(b'{"t":"intent","id":"2","at":"now","objective":"obj2"}\n')

    with pytest.raises(CorruptLogLine):
        store.read_events()


def test_torn_final_line_read(tmp_path: Path) -> None:
    # 21. Torn final line - read. A torn write leaves a structurally incomplete,
    # unterminated tail (the final newline never landed).
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    with open(paths.log, "wb") as f:
        f.write(b'{"t":"intent","id":"1","at":"now","objective":"obj"}\n')
        f.write(b'{"t":"intent"')  # no trailing \n, incomplete JSON

    res = store.read_events()
    assert len(res.events) == 1
    assert res.events[0].id == "1"
    assert res.torn is not None
    assert res.torn.raw == b'{"t":"intent"'


def test_schema_invalid_final_line_raises_not_torn(tmp_path: Path) -> None:
    # A fully written (newline-terminated) line that is valid JSON but violates the
    # event schema is a contract violation, not a torn tail: it must raise loudly so
    # it can never be silently quarantined and dropped.
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    with open(paths.log, "wb") as f:
        f.write(b'{"t":"intent","id":"1","at":"now","objective":"obj"}\n')
        f.write(b'{"t":"intent"}\n')  # valid JSON, missing required fields

    with pytest.raises(SchemaError) as excinfo:
        store.read_events()
    # The diagnostic must locate the offending line and carry the underlying cause.
    assert "line 2" in str(excinfo.value)


def test_schema_invalid_midlog_raises_schema_not_corrupt(tmp_path: Path) -> None:
    # Valid JSON with an unknown event type is a schema violation (SchemaError),
    # distinct from structurally broken bytes (CorruptLogLine).
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    with open(paths.log, "wb") as f:
        f.write(b'{"t":"intent","id":"1","at":"now","objective":"obj"}\n')
        f.write(b'{"t":"bogus","id":"2","at":"now"}\n')
        f.write(b'{"t":"intent","id":"3","at":"now","objective":"obj3"}\n')

    with pytest.raises(SchemaError):
        store.read_events()


def test_append_after_torn(tmp_path: Path) -> None:
    # 22. Append after torn.
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    with open(paths.log, "wb") as f:
        f.write(b'{"t":"intent","id":"1","at":"now","objective":"obj"}\n')
        f.write(b'{"t":"intent"')

    res = store.read_events()
    assert res.torn is not None

    store.quarantine_and_truncate(res.torn, "20260605T123000Z")

    store.append_line('{"t":"intent","id":"2","at":"now","objective":"obj2"}')

    res2 = store.read_events()
    assert res2.torn is None
    assert len(res2.events) == 2
    assert res2.events[1].id == "2"

    corrupt_file = paths.capsule_dir / "log.jsonl.corrupt-20260605T123000Z"
    assert corrupt_file.is_file()
    assert corrupt_file.read_bytes() == b'{"t":"intent"'


def test_atomic_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 27. Atomic render.
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    # Track os.replace
    replaces = []
    original_replace = os.replace

    def mock_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaces.append((Path(src), Path(dst)))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)

    store.write_render("Hello World")

    assert len(replaces) == 1
    src, dst = replaces[0]
    assert src.parent == paths.capsule_dir
    assert dst == paths.render

    assert paths.render.read_text(encoding="utf-8") == "Hello World"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file sharing semantics")
def test_atomic_render_recovers_after_windows_reader_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()
    store.write_render("old render")
    original_replace = os.replace
    attempts = 0

    with paths.render.open("rb") as reader:

        def replace_while_reading(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            nonlocal attempts
            attempts += 1
            try:
                original_replace(src, dst)
            except PermissionError:
                # Release a real Windows handle that prevented the first replacement.
                reader.close()
                raise

        monkeypatch.setattr(os, "replace", replace_while_reading)
        store.write_render("new render")

    assert attempts >= 2
    assert paths.render.read_text(encoding="utf-8") == "new render"
    assert set(paths.capsule_dir.iterdir()) == {paths.log, paths.render}


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_atomic_render_retries_windows_file_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, winerror: int
) -> None:
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()
    store.write_render("old render")
    original_replace = os.replace
    attempts = 0

    def busy_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            assert paths.render.read_text(encoding="utf-8") == "old render"
            error = PermissionError(errno.EACCES, "render is temporarily in use")
            error.winerror = winerror
            raise error
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", busy_replace)
    store.write_render("new render")

    assert attempts == 3
    assert paths.render.read_text(encoding="utf-8") == "new render"
    assert set(paths.capsule_dir.iterdir()) == {paths.log, paths.render}


def test_atomic_render_stops_retrying_persistent_windows_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()
    store.write_render("old render")
    elapsed = 0.0
    attempts = 0

    def advance_time(delay: float) -> None:
        nonlocal elapsed
        elapsed += delay

    monkeypatch.setattr(
        store_module, "time", SimpleNamespace(monotonic=lambda: elapsed, sleep=advance_time)
    )

    def denied_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal attempts
        attempts += 1
        error = PermissionError(errno.EACCES, "access remains denied")
        error.winerror = 5
        raise error

    monkeypatch.setattr(os, "replace", denied_replace)
    with pytest.raises(CapsuleError, match="failed to write render"):
        store.write_render("new render")

    assert attempts > 1
    assert elapsed <= 1.1
    assert paths.render.read_text(encoding="utf-8") == "old render"
    assert set(paths.capsule_dir.iterdir()) == {paths.log, paths.render}


@pytest.mark.parametrize("error_number", [errno.EACCES, errno.ENOENT, errno.ENOSPC])
def test_atomic_render_does_not_retry_other_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_number: int
) -> None:
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()
    store.write_render("old render")
    attempts = 0

    def failed_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal attempts
        attempts += 1
        raise OSError(error_number, "replacement failed")

    monkeypatch.setattr(os, "replace", failed_replace)
    with pytest.raises(CapsuleError, match="failed to write render"):
        store.write_render("new render")

    assert attempts == 1
    assert paths.render.read_text(encoding="utf-8") == "old render"
    assert set(paths.capsule_dir.iterdir()) == {paths.log, paths.render}


def test_cross_platform_paths() -> None:
    # 28. Cross-platform paths. POSIX and Windows styles.
    p_posix = CapsulePaths.for_repo(Path("/tmp/myrepo"))
    p_win = CapsulePaths.for_repo(Path("C:\\tmp\\myrepo"))

    assert p_posix.capsule_dir.name == ".capsule"
    assert p_posix.log.name == "log.jsonl"
    assert p_win.capsule_dir.name == ".capsule"
    assert p_win.log.name == "log.jsonl"


def test_newline_utf8_integrity(tmp_path: Path) -> None:
    # 29. Newline/UTF-8 integrity.
    paths = CapsulePaths.for_repo(tmp_path)
    store = Store(paths)
    store.create()

    unicode_text = '{"t":"intent","id":"1","at":"now","objective":"— ✨"}'
    store.append_line(unicode_text)

    # Read binary and verify it's UTF-8 and exactly ends with \n
    b = paths.log.read_bytes()
    expected_b = unicode_text.encode("utf-8") + b"\n"
    assert b == expected_b

    store.write_render("— ✨\n")
    render_b = paths.render.read_bytes()
    assert render_b == "— ✨\n".encode()


def test_rejects_capsule_dir_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    escape_link = repo / ".capsule"
    try:
        escape_link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    paths = CapsulePaths.for_repo(repo)
    store = Store(paths)
    with pytest.raises(CapsuleError, match="resolves outside repo root"):
        store.create()


def test_rejects_log_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    capsule_dir = repo / ".capsule"
    capsule_dir.mkdir()
    log_link = capsule_dir / "log.jsonl"
    try:
        log_link.symlink_to(outside / "log.jsonl")
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    paths = CapsulePaths.for_repo(repo)
    store = Store(paths)
    with pytest.raises(CapsuleError, match="resolves outside repo root"):
        store.append_line('{"t":"intent","id":"1","at":"now","objective":"obj"}')


def test_rejects_log_symlink_escape_on_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    capsule_dir = repo / ".capsule"
    capsule_dir.mkdir()
    log_link = capsule_dir / "log.jsonl"
    try:
        log_link.symlink_to(outside / "log.jsonl")
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    paths = CapsulePaths.for_repo(repo)
    store = Store(paths)
    with pytest.raises(CapsuleError, match="resolves outside repo root"):
        store.read_events()
