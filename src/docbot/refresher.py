"""Periodic refresh of verification repos."""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

log = logging.getLogger(__name__)


class RepoRefresher:
    def __init__(self, repos: list[Path], interval_sec: int = 4 * 3600) -> None:
        self.repos = repos
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def refresh_once(self) -> None:
        for repo in self.repos:
            self._refresh(repo)

    def _refresh(self, repo: Path) -> None:
        """Fetch origin and reset --hard to origin/master. If origin is unreachable
        (e.g., test environment or first-boot), fall back to a local reset so the
        working tree is at least clean."""
        fetched = False
        try:
            subprocess.run(["git", "fetch", "origin"], cwd=repo, check=True, capture_output=True)
            fetched = True
        except subprocess.CalledProcessError as e:
            log.warning(
                "fetch failed; falling back to local reset",
                extra={"repo": str(repo), "err": e.stderr.decode(errors="ignore") if e.stderr else ""},
            )

        target = "origin/master" if fetched else "HEAD"
        try:
            subprocess.run(["git", "reset", "--hard", target], cwd=repo, check=True, capture_output=True)
            log.info("refreshed", extra={"repo": str(repo), "target": target})
        except subprocess.CalledProcessError as e:
            log.warning(
                "reset failed",
                extra={"repo": str(repo), "err": e.stderr.decode(errors="ignore") if e.stderr else ""},
            )

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh_once()
            self._stop.wait(self.interval_sec)
