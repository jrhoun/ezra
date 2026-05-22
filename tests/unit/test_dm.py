from unittest.mock import MagicMock

from docbot.slack.dm import DMSender


def test_dm_sends_to_reactor_when_no_default():
    client = MagicMock()
    client.conversations_open.return_value = {"channel": {"id": "D1"}}
    sender = DMSender(client=client, default_user=None, dry_run=False, dry_run_dir=None)
    sender.send(
        reactor_user="U_REACTOR",
        outcome="could_not_verify",
        reasoning="The doc seems fine. The flag still exists at portal-impl/...",
        permalink="https://slack.example/p1",
        verified_against=["liferay-portal:feature.flag.foo"],
    )
    client.conversations_open.assert_called_once_with(users="U_REACTOR")
    client.chat_postMessage.assert_called_once()
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "D1"
    assert "could_not_verify" in kwargs["text"]
    assert "https://slack.example/p1" in kwargs["text"]


def test_dm_sends_to_default_user_when_configured():
    client = MagicMock()
    client.conversations_open.return_value = {"channel": {"id": "D_DEFAULT"}}
    sender = DMSender(client=client, default_user="U_DEFAULT", dry_run=False, dry_run_dir=None)
    sender.send(reactor_user="U_REACTOR", outcome="no_change_needed",
                reasoning="x", permalink="p", verified_against=[])
    client.conversations_open.assert_called_once_with(users="U_DEFAULT")


def test_dm_dry_run_writes_to_log(tmp_path):
    sender = DMSender(client=None, default_user=None, dry_run=True, dry_run_dir=tmp_path)
    sender.send(reactor_user="U_REACTOR", outcome="could_not_verify",
                reasoning="r", permalink="p", verified_against=[])
    files = list(tmp_path.iterdir())
    assert len(files) == 1


import pytest
from slack_sdk.errors import SlackApiError

from docbot.slack.dm import DMError


def _slack_err(code: str) -> SlackApiError:
    return SlackApiError(message=code, response={"ok": False, "error": code})


def test_conversations_open_failure_raises_structured_dm_error(tmp_path):
    """A failure in conversations_open is wrapped in DMError with the right kind."""
    client = MagicMock()
    client.conversations_open.side_effect = _slack_err("user_not_found")
    sender = DMSender(client=client, default_user=None, dry_run=False, dry_run_dir=None)
    with pytest.raises(DMError) as excinfo:
        sender.send(reactor_user="U_BAD", outcome="x", reasoning="r",
                    permalink="p", verified_against=[])
    err = excinfo.value
    assert err.kind == "conversations_open_failed"
    assert err.slack_error == "user_not_found"


def test_post_message_failure_raises_structured_dm_error(tmp_path):
    """A failure in chat_postMessage after a successful open is wrapped distinctly."""
    client = MagicMock()
    client.conversations_open.return_value = {"channel": {"id": "D1"}}
    client.chat_postMessage.side_effect = _slack_err("rate_limited")
    sender = DMSender(client=client, default_user=None, dry_run=False, dry_run_dir=None)
    with pytest.raises(DMError) as excinfo:
        sender.send(reactor_user="U", outcome="x", reasoning="r",
                    permalink="p", verified_against=[])
    err = excinfo.value
    assert err.kind == "post_failed"
    assert err.slack_error == "rate_limited"
