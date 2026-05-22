import subprocess
from pathlib import Path

import pytest

from docbot.worktree.pool import WorktreePool, NoWorktreeAvailable


@pytest.fixture
def base_repo(tmp_path: Path) -> Path:
    """A minimal git repo with one commit on master."""
    repo = tmp_path / "base"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "master"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("hi\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True)
    return repo


def test_pool_initializes_n_worktrees(tmp_path, base_repo):
    pool = WorktreePool(base_repo=base_repo, root=tmp_path / "wts", size=3)
    pool.start()
    try:
        worktrees = list((tmp_path / "wts").iterdir())
        assert len(worktrees) == 3
    finally:
        pool.shutdown()


def test_claim_returns_worktree_on_new_branch(tmp_path, base_repo):
    pool = WorktreePool(base_repo=base_repo, root=tmp_path / "wts", size=1)
    pool.start()
    try:
        wt = pool.claim(branch_slug="fix-typo")
        assert wt.path.exists()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=wt.path, check=True, capture_output=True, text=True
        ).stdout.strip()
        assert branch.startswith("docbot/")
        assert branch.endswith("-fix-typo") or "-fix-typo-" in branch
        pool.release(wt)
    finally:
        pool.shutdown()


def test_claim_empty_pool_raises(tmp_path, base_repo):
    pool = WorktreePool(base_repo=base_repo, root=tmp_path / "wts", size=1)
    pool.start()
    try:
        pool.claim(branch_slug="a")
        with pytest.raises(NoWorktreeAvailable):
            pool.claim(branch_slug="b")
    finally:
        pool.shutdown()


def test_release_resets_dirty_worktree(tmp_path, base_repo):
    pool = WorktreePool(base_repo=base_repo, root=tmp_path / "wts", size=1)
    pool.start()
    try:
        wt = pool.claim(branch_slug="x")
        (wt.path / "junk.txt").write_text("dirty\n")
        pool.release(wt)
        wt2 = pool.claim(branch_slug="y")
        assert not (wt2.path / "junk.txt").exists()
        pool.release(wt2)
    finally:
        pool.shutdown()
