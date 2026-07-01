import json
import subprocess
from pathlib import Path
from typing import Any

from capsule.exit_codes import ExitCode


def test_tp1_init_repo_dot(invoke_main: Any, tmp_path: Path) -> None:
    """T-P1: init --repo . from a named dir -> resolved dir name."""
    proj_dir = tmp_path / "my-project"
    proj_dir.mkdir()

    # We must use invoke_main to change cwd properly in process, or pass cwd.
    res = invoke_main(
        ["--repo", ".", "--format", "json", "init", "--draft", "git", "--no-git"], cwd=str(proj_dir)
    )
    assert res.exit_code == 0

    # Check the recorded intent using the absolute path since we're outside now
    res_load = invoke_main(["--repo", str(proj_dir), "--format", "json", "load"])
    assert res_load.exit_code == 0
    payload = json.loads(res_load.stdout)

    # The heuristic should use the directory name if it's sparse
    assert "my-project" in payload["objective"]
    assert "Continue work in" in payload["objective"]


def test_ts1_sparse_readme_only(invoke_main: Any, tmp_path: Path) -> None:
    """T-S1: README-only sparse repo."""
    proj_dir = tmp_path / "sparse-repo"
    proj_dir.mkdir()
    (proj_dir / "README.md").write_text("# My Awesome Project\n\nSome text.", encoding="utf-8")
    (proj_dir / "src").mkdir()
    (proj_dir / "tests").mkdir()

    res = invoke_main(
        ["--repo", str(proj_dir), "--format", "json", "init", "--draft", "git", "--no-git"]
    )
    assert res.exit_code == 0

    res_load = invoke_main(["--repo", str(proj_dir), "--format", "json", "load"])
    assert res_load.exit_code == 0
    payload = json.loads(res_load.stdout)

    assert payload["objective"] == "My Awesome Project"
    # Should include src and tests as top-level modules
    understanding = "\n".join(payload["current_understanding"])
    assert "top-level modules: src, tests" in understanding


def test_ts2_truly_sparse(invoke_main: Any, tmp_path: Path) -> None:
    """T-S2: truly sparse."""
    proj_dir = tmp_path / "empty-project"
    proj_dir.mkdir()

    res = invoke_main(
        ["--repo", str(proj_dir), "--format", "json", "init", "--draft", "git", "--no-git"]
    )
    assert res.exit_code == 0

    res_load = invoke_main(["--repo", str(proj_dir), "--format", "json", "load"])
    assert res_load.exit_code == 0
    payload = json.loads(res_load.stdout)

    assert payload["objective"] == "Continue work in empty-project"


def test_th5_init_git_repo(invoke_cli: Any, tmp_path: Any) -> None:
    """T-H5: init cold-start (fixture git repo)."""
    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "first commit"], cwd=tmp_path, check=True)

    res = invoke_cli(["--repo", str(tmp_path), "--format", "json", "init", "--draft", "git"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["draft_source"] == "git-heuristic"

    # Check intent
    res_load = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    load_payload = json.loads(res_load.stdout)
    assert "drafted from git history" in load_payload["current_understanding"][0]


def test_tf7_init_exists_without_force(invoke_cli: Any, tmp_path: Any) -> None:
    """T-F7: init exists-without-force -> exit 1, log not clobbered."""
    invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])
    invoke_cli(["--repo", str(tmp_path), "record", "intent", "--objective", "old"])

    res = invoke_cli(["--repo", str(tmp_path), "init", "--draft", "none"])
    assert res.exit_code == ExitCode.ERROR
    assert "already exists" in res.stderr

    res_load = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    assert json.loads(res_load.stdout)["objective"] == "old"

    # with force
    res2 = invoke_cli(["--repo", str(tmp_path), "init", "--force", "--draft", "git", "--no-git"])
    assert res2.exit_code == 0
    res_load2 = invoke_cli(["--repo", str(tmp_path), "--format", "json", "load"])
    assert json.loads(res_load2.stdout)["objective"] != "old"
