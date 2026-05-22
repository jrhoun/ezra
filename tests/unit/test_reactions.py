from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from docbot.slack.reactions import claim_message, mark_done


def _mock_error(code: str) -> SlackApiError:
    return SlackApiError(message=code, response={"ok": False, "error": code})


def test_claim_returns_true_when_emoji_added():
    client = MagicMock()
    client.reactions_add.return_value = {"ok": True}
    assert claim_message(client, channel="C1", ts="123.456", emoji="docbot-thinking") is True


def test_claim_returns_false_when_already_reacted():
    client = MagicMock()
    client.reactions_add.side_effect = _mock_error("already_reacted")
    assert claim_message(client, channel="C1", ts="123.456", emoji="docbot-thinking") is False


def test_claim_reraises_other_errors():
    client = MagicMock()
    client.reactions_add.side_effect = _mock_error("missing_scope")
    with pytest.raises(SlackApiError):
        claim_message(client, channel="C1", ts="123.456", emoji="docbot-thinking")


def test_mark_done_removes_processing_and_adds_done():
    client = MagicMock()
    mark_done(client, channel="C1", ts="123.456",
              processing="docbot-thinking", done="docbot-done")
    client.reactions_remove.assert_called_once_with(
        channel="C1", timestamp="123.456", name="docbot-thinking"
    )
    client.reactions_add.assert_called_once_with(
        channel="C1", timestamp="123.456", name="docbot-done"
    )
