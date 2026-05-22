"""Worktree pool over a base git repo.

Maintains N pre-created worktrees of a base repo. Each claim returns a
fresh branch off `origin/master`; each release hard-resets the worktree
back to a clean state so it can be reused.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


class NoWorktreeAvailable(Exception):
    pass


@dataclass
class Worktree:
    path: Path
    branch: str


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


class WorktreePool:
    def __init__(self, base_repo: Path, root: Path, size: int) -> None:
        self.base_repo = base_repo
        self.root = root
        self.size = size
        self._available: list[Path] = []
        self._claimed: dict[Path, Worktree] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for i in range(self.size):
            wt_path = self.root / f"docbot-{i}"
            if not wt_path.exists():
                _run(["git", "worktree", "add", "-f", str(wt_path), "master"], cwd=self.base_repo)
            self._available.append(wt_path)

    def shutdown(self) -> None:
        with self._lock:
            for wt_path in list(self._available) + [w.path for w in self._claimed.values()]:
                try:
                    _run(["git", "worktree", "remove", "-f", str(wt_path)], cwd=self.base_repo)
                except subprocess.CalledProcessError as e:
                    log.warning("worktree remove failed", extra={"path": str(wt_path), "err": e.stderr})

    def claim(self, branch_slug: str) -> Worktree:
        with self._lock:
            if not self._available:
                raise NoWorktreeAvailable("pool exhausted")
            path = self._available.pop()

        ts = int(time.time())
        branch = f"docbot/{ts}-{branch_slug}-{uuid.uuid4().hex[:6]}"
        _run(["git", "checkout", "-B", branch, "master"], cwd=path)
        wt = Worktree(path=path, branch=branch)
        with self._lock:
            self._claimed[path] = wt
        return wt

    def release(self, wt: Worktree) -> None:
        try:
            _run(["git", "reset", "--hard", "master"], cwd=wt.path)
            _run(["git", "clean", "-fdx"], cwd=wt.path)
        except subprocess.CalledProcessError as e:
            log.warning("worktree reset failed", extra={"path": str(wt.path), "err": e.stderr})
        with self._lock:
            self._claimed.pop(wt.path, None)
            self._available.append(wt.path)
