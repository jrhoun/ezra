"""Subprocess wrapper around the headless `claude` CLI.

Spawns claude with a prompt, waits with a wall-clock timeout, and
extracts the structured outcome from the final JSON line of stdout.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


class ClaudeError(Exception):
    pass


@dataclass
class ClaudeOutcome:
    outcome: str
    reasoning: str
    files_changed: list[str]
    commit_sha: str
    verified_against: list[str]


class ClaudeRunner:
    def __init__(
        self,
        binary: str,
        timeout_sec: int,
        max_turns: int,
        allowed_tools: list[str],
    ) -> None:
        self.binary = binary
        self.timeout_sec = timeout_sec
        self.max_turns = max_turns
        self.allowed_tools = allowed_tools

    def run(self, workdir: Path, prompt: str) -> ClaudeOutcome:
        cmd = [self.binary, "-p", prompt]
        # NOTE: confirm exact flag syntax against the headless claude CLI
        # in use; --max-turns and --allowed-tools may differ.
        if self.max_turns:
            cmd.extend(["--max-turns", str(self.max_turns)])
        for tool in self.allowed_tools:
            cmd.extend(["--allowed-tools", tool])

        try:
            result = subprocess.run(
                cmd,
                cwd=workdir,
                timeout=self.timeout_sec,
                check=False,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired as e:
            log.warning("claude timeout", extra={"workdir": str(workdir)})
            raise ClaudeError(f"timeout after {self.timeout_sec}s") from e

        if result.returncode != 0:
            raise ClaudeError(
                f"claude exited {result.returncode}: {result.stderr[-2000:]}"
            )

        return self._parse(result.stdout)

    def _parse(self, stdout: str) -> ClaudeOutcome:
        lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
        for line in reversed(lines):
            try:
                data = json.loads(line)
                return ClaudeOutcome(
                    outcome=data["outcome"],
                    reasoning=data.get("reasoning", ""),
                    files_changed=data.get("files_changed", []),
                    commit_sha=data.get("commit_sha", ""),
                    verified_against=data.get("verified_against", []),
                )
            except (json.JSONDecodeError, KeyError):
                continue
        raise ClaudeError(f"unparseable claude output (last 500 chars): {stdout[-500:]}")
