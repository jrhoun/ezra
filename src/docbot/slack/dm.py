"""Slack DM sender — used for non-success outcomes."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from slack_sdk import WebClient

log = logging.getLogger(__name__)


class DMSender:
    def __init__(
        self,
        client: Optional[WebClient],
        default_user: Optional[str],
        dry_run: bool,
        dry_run_dir: Optional[Path],
    ) -> None:
        self.client = client
        self.default_user = default_user
        self.dry_run = dry_run
        self.dry_run_dir = dry_run_dir

    def send(
        self,
        reactor_user: str,
        outcome: str,
        reasoning: str,
        permalink: str,
        verified_against: list[str],
    ) -> None:
        target_user = self.default_user or reactor_user
        text = self._format(outcome, reasoning, permalink, verified_against)

        if self.dry_run:
            assert self.dry_run_dir is not None
            self.dry_run_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "target_user": target_user,
                "outcome": outcome,
                "text": text,
                "permalink": permalink,
            }
            out = self.dry_run_dir / f"{int(time.time())}-dm-{target_user}.json"
            out.write_text(json.dumps(payload, indent=2))
            return

        assert self.client is not None
        opened = self.client.conversations_open(users=target_user)
        channel_id = opened["channel"]["id"]
        self.client.chat_postMessage(channel=channel_id, text=text)

    @staticmethod
    def _format(outcome: str, reasoning: str, permalink: str, verified_against: list[str]) -> str:
        lines = [
            f"*Outcome:* `{outcome}`",
            f"*Reported in:* {permalink}",
            "",
            reasoning,
        ]
        if verified_against:
            lines.append("")
            lines.append("*Verified against:*")
            for v in verified_against:
                lines.append(f"• `{v}`")
        return "\n".join(lines)
