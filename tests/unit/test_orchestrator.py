from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docbot.orchestrator.orchestrator import Orchestrator, Event
from docbot.claude_runner.runner import ClaudeOutcome, ClaudeError
from docbot.worktree.pool import Worktree


@pytest.fixture
def orchestrator_components(tmp_path):
    pool = MagicMock()
    pool.claim.return_value = Worktree(path=tmp_path, branch="docbot/123-x")
    claude = MagicMock()
    pr_opener = MagicMock()
    dm_sender = MagicMock()
    slack_client = MagicMock()
    # By default the claim attempt succeeds.
    slack_client.reactions_add.return_value = {"ok": True}
    return pool, claude, pr_opener, dm_sender, slack_client


def test_pr_ready_outcome_opens_pr(orchestrator_components, tmp_path):
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.return_value = ClaudeOutcome(
        outcome="pr_ready",
        reasoning="r",
        files_changed=["docs/x.md"],
        commit_sha="abc",
        verified_against=["liferay-portal:y"],
    )
    pr_opener.open.return_value = "https://github.com/x/y/pull/1"

    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="msg={message_text} url={permalink}",
    )
    orch.handle(Event(
        channel="C1", message_ts="123.456", reactor_user="U1",
        message_text="LPS-X is wrong", permalink="https://slack/p",
    ))

    pr_opener.open.assert_called_once()
    dm_sender.send.assert_not_called()


def test_could_not_verify_outcome_dms_reactor(orchestrator_components, tmp_path):
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.return_value = ClaudeOutcome(
        outcome="could_not_verify",
        reasoning="r", files_changed=[], commit_sha="", verified_against=[],
    )
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    pr_opener.open.assert_not_called()
    dm_sender.send.assert_called_once()


def test_claude_error_treated_as_could_not_verify(orchestrator_components):
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.side_effect = ClaudeError("timeout after 900s", kind="timeout")
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    pr_opener.open.assert_not_called()
    dm_sender.send.assert_called_once()
    args = dm_sender.send.call_args.kwargs
    assert "timeout" in args["reasoning"].lower()
