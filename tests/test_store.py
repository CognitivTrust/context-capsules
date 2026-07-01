import os
from pathlib import Path

import pytest

from capsule.engine.errors import CapsuleError, CorruptLogLine, SchemaError
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
