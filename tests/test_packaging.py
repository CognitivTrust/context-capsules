import importlib.metadata

import capsule


def test_version_matches_metadata() -> None:
    dist_version = importlib.metadata.version("context-capsule")
    assert capsule.__version__ == dist_version
    assert isinstance(capsule.__version__, str)
    assert len(capsule.__version__) > 0


def test_entrypoint_resolves() -> None:
    eps = importlib.metadata.entry_points(group="console_scripts")
    # depending on python version, it might return a tuple or SelectableGroups
    capsule_eps = [ep for ep in eps if ep.name == "capsule"]
    assert len(capsule_eps) == 1
    ep = capsule_eps[0]
    assert ep.module == "capsule.cli.app"
    assert ep.attr == "main"
