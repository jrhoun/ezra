"""Slack reaction-based claim/done helpers — the idempotency mechanism."""

from __future__ import annotations

import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log = logging.getLogger(__name__)


def claim_message(client: WebClient, channel: str, ts: str, emoji: str) -> bool:
    """Attempt to add the processing emoji. Return True if added, False if
    another worker already claimed it. Re-raise other Slack errors."""
    try:
        client.reactions_add(channel=channel, timestamp=ts, name=emoji)
        return True
    except SlackApiError as e:
        if e.response.get("error") == "already_reacted":
            return False
        raise


def mark_done(
    client: WebClient,
    channel: str,
    ts: str,
    processing: str,
    done: str,
) -> None:
    """Replace the processing emoji with the done emoji."""
    try:
        client.reactions_remove(channel=channel, timestamp=ts, name=processing)
    except SlackApiError as e:
        log.warning("reactions_remove failed", extra={"err": e.response.get("error")})
    try:
        client.reactions_add(channel=channel, timestamp=ts, name=done)
    except SlackApiError as e:
        if e.response.get("error") != "already_reacted":
            log.warning("reactions_add(done) failed", extra={"err": e.response.get("error")})
