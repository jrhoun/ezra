"""GitHub PR creation: git push to fork, then `gh pr create` upstream."""

from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


class PRError(Exception):
    """Raised when git push or gh pr create fails. Carries a `kind`
    discriminator so the orchestrator can distinguish push failures from
    PR-create failures, plus the returncode and stderr from the failing
    subprocess."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        returncode: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind  # one of: "push_failed" | "gh_create_failed"
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class PRRequest:
    workdir: Path
    branch: str
    title_subject: str
    body: str


class PROpener:
    def __init__(
        self,
        fork_owner: str,
        upstream_repo: str,
        base_branch: str,
        pr_label: str,
        pr_title_prefix: str,
        dry_run: bool,
        dry_run_dir: Path,
        fork_remote: str | None = None,
    ) -> None:
        self.fork_owner = fork_owner
        self.upstream_repo = upstream_repo
        self.base_branch = base_branch
        self.pr_label = pr_label
        self.pr_title_prefix = pr_title_prefix
        self.dry_run = dry_run
        self.dry_run_dir = dry_run_dir
        self.fork_remote = fork_remote or f"{fork_owner}-fork"

    def open(self, req: PRRequest) -> str:
        title = f"{self.pr_title_prefix} {req.title_subject}".strip()

        if self.dry_run:
            self.dry_run_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "branch": req.branch,
                "title": title,
                "body": req.body,
                "label": self.pr_label,
                "fork_owner": self.fork_owner,
                "upstream_repo": self.upstream_repo,
            }
            out = self.dry_run_dir / f"{int(time.time())}-{uuid.uuid4().hex[:8]}-{req.branch.replace('/', '-')}.json"
            out.write_text(json.dumps(payload, indent=2))
            return f"dry-run://{req.branch}"

        # Push branch to fork
        push_cmd = ["git", "push", self.fork_remote, req.branch]
        result = subprocess.run(push_cmd, cwd=req.workdir, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise PRError(
                f"git push to {self.fork_remote} failed",
                kind="push_failed",
                returncode=result.returncode,
                stderr=result.stderr,
            )

        # Create PR upstream
        gh_cmd = [
            "gh", "pr", "create",
            "--repo", self.upstream_repo,
            "--base", self.base_branch,
            "--head", f"{self.fork_owner}:{req.branch}",
            "--title", title,
            "--body", req.body,
            "--label", self.pr_label,
        ]
        result = subprocess.run(gh_cmd, cwd=req.workdir, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise PRError(
                "gh pr create failed",
                kind="gh_create_failed",
                returncode=result.returncode,
                stderr=result.stderr,
            )

        return result.stdout.strip()
