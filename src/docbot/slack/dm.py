"""Slack DM sender — used for non-success outcomes."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log = logging.getLogger(__name__)


class DMError(Exception):
    """Raised when DM delivery fails. Carries a `kind` so the orchestrator
    can distinguish conversations_open failures (e.g., user doesn't allow
    DMs, invalid user ID) from chat_postMessage failures (e.g., rate limit,
    archived channel)."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        slack_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind  # one of: "conversations_open_failed" | "post_failed"
        self.slack_error = slack_error


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
            if self.dry_run_dir is None:
                raise RuntimeError("DMSender is in dry-run mode but dry_run_dir is None")
            self.dry_run_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "target_user": target_user,
                "outcome": outcome,
                "text": text,
                "permalink": permalink,
            }
            out = self.dry_run_dir / f"{int(time.time())}-{uuid.uuid4().hex[:8]}-dm-{target_user}.json"
            out.write_text(json.dumps(payload, indent=2))
            return

        if self.client is None:
            raise RuntimeError("DMSender is in live mode but client is None")

        try:
            opened = self.client.conversations_open(users=target_user)
        except SlackApiError as e:
            raise DMError(
                f"conversations_open failed for {target_user}",
                kind="conversations_open_failed",
                slack_error=e.response.get("error") if e.response else None,
            ) from e

        channel_id = opened["channel"]["id"]
        try:
            self.client.chat_postMessage(channel=channel_id, text=text)
        except SlackApiError as e:
            raise DMError(
                f"chat_postMessage failed for {target_user}",
                kind="post_failed",
                slack_error=e.response.get("error") if e.response else None,
            ) from e

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
