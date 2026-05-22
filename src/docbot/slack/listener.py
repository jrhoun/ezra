"""Slack Socket Mode listener wired to the orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from docbot.orchestrator.orchestrator import Event, Orchestrator

log = logging.getLogger(__name__)


def build_app(
    bot_token: str,
    app_token: str,
    watch_channel_id: str,
    trigger_emoji: str,
    max_message_age_days: int,
    orchestrator: Orchestrator,
) -> SocketModeHandler:
    app = App(token=bot_token)

    @app.event("reaction_added")
    def on_reaction(event, client, logger):
        if event.get("reaction") != trigger_emoji:
            return
        item = event.get("item", {})
        if item.get("type") != "message":
            return
        channel = item.get("channel")
        if channel != watch_channel_id:
            return
        ts = item.get("ts")
        reactor = event.get("user")
        if not ts or not reactor:
            return

        try:
            message_text, permalink = _fetch_context(client, channel, ts)
        except Exception as e:
            log.warning("could not fetch message context", extra={"err": str(e), "ts": ts})
            return

        if _too_old(ts, max_message_age_days):
            log.info("message too old, dropping", extra={"ts": ts})
            return

        orchestrator.handle(Event(
            channel=channel, message_ts=ts, reactor_user=reactor,
            message_text=message_text, permalink=permalink,
        ))

    return SocketModeHandler(app, app_token)


def _fetch_context(client, channel: str, ts: str) -> tuple[str, str]:
    """Fetch message text + permalink, including the thread parent if this is a reply."""
    resp = client.conversations_replies(channel=channel, ts=ts, limit=1)
    messages = resp.get("messages") or []
    if not messages:
        raise RuntimeError("message not found")
    msg = messages[0]

    text = msg.get("text", "")
    # If this is a thread reply, prepend the parent's text.
    thread_ts = msg.get("thread_ts")
    if thread_ts and thread_ts != ts:
        parent = client.conversations_replies(channel=channel, ts=thread_ts, limit=1)
        parent_msgs = parent.get("messages") or []
        if parent_msgs:
            text = f"[Thread parent]\n{parent_msgs[0].get('text', '')}\n\n[Replied to]\n{text}"

    permalink_resp = client.chat_getPermalink(channel=channel, message_ts=ts)
    permalink = permalink_resp.get("permalink", "")
    return text, permalink


def _too_old(ts: str, max_days: int) -> bool:
    msg_time = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - msg_time
    return age.days > max_days
