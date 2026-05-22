import subprocess
from pathlib import Path

import pytest

from docbot.refresher import RepoRefresher


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "master"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f").write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True)


def test_refresher_resets_dirty_repos(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "f").write_text("dirty")
    refresher = RepoRefresher(repos=[repo])
    refresher.refresh_once()
    assert (repo / "f").read_text() == "x"
