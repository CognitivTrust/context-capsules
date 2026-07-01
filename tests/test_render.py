import json
import multiprocessing
from pathlib import Path

from capsule.engine.events import Event
from capsule.engine.fold import fold
from capsule.engine.render import render
from capsule.engine.schema import from_obj


def _load_events(path: Path) -> tuple[Event, ...]:
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    return tuple(from_obj(json.loads(line)) for line in lines)


def test_render_golden_bytes() -> None:
    # 5. `render` golden bytes.
    # empty projection
    empty_md_path = Path(__file__).parent / "fixtures" / "empty.md"
    with open(empty_md_path, encoding="utf-8") as f:
        expected_empty = f.read()

    empty_proj = fold(())
    actual_empty = render(empty_proj)
    assert actual_empty == expected_empty

    # canonical projection
    canonical_jsonl_path = Path(__file__).parent / "fixtures" / "canonical.jsonl"
    canonical_md_path = Path(__file__).parent / "fixtures" / "canonical.md"
    events = _load_events(canonical_jsonl_path)
    proj = fold(events)

    with open(canonical_md_path, encoding="utf-8") as f:
        expected_canonical = f.read()

    actual_canonical = render(proj)
    assert actual_canonical == expected_canonical


def test_empty_log_render_stability() -> None:
    # 6. Empty log render stability. Re-rendering the empty
    # projection is byte-identical across repeated calls.
    empty_proj = fold(())
    r1 = render(empty_proj)
    r2 = render(empty_proj)
    assert r1 == r2


def _subprocess_render(fixture_path: Path) -> str:
    events = _load_events(fixture_path)
    proj = fold(events)
    return render(proj)


def test_render_stability_across_processes() -> None:
    # 11. Render stability across runs/processes.
    canonical_jsonl_path = Path(__file__).parent / "fixtures" / "canonical.jsonl"
    events = _load_events(canonical_jsonl_path)
    proj = fold(events)
    expected = render(proj)

    with multiprocessing.Pool(1) as pool:
        actual = pool.apply(_subprocess_render, (canonical_jsonl_path,))

    assert actual == expected
