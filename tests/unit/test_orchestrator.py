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


from docbot.worktree.pool import NoWorktreeAvailable


def test_already_claimed_drops_event(orchestrator_components):
    """If claim_message returns False (already_reacted), no pool/claude/DM/PR action runs."""
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    from slack_sdk.errors import SlackApiError
    slack.reactions_add.side_effect = SlackApiError(
        message="already_reacted",
        response={"ok": False, "error": "already_reacted"},
    )
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    pool.claim.assert_not_called()
    claude.run.assert_not_called()
    dm_sender.send.assert_not_called()
    pr_opener.open.assert_not_called()


def test_pool_exhausted_dms_busy_and_marks_done(orchestrator_components, tmp_path):
    """If the worktree pool is exhausted, the orchestrator DMs a 'busy' message
    and still marks the message done so it doesn't loop on retry."""
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    pool.claim.side_effect = NoWorktreeAvailable("pool exhausted")
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    dm_sender.send.assert_called_once()
    kwargs = dm_sender.send.call_args.kwargs
    assert "busy" in kwargs["reasoning"].lower()
    # Done emoji should be applied so the message isn't retried forever.
    slack.reactions_remove.assert_called()


def test_pool_release_runs_even_on_claude_error(orchestrator_components):
    """The pool.release call in the finally block must run even when Claude raises."""
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.side_effect = ClaudeError("timeout", kind="timeout")
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    pool.release.assert_called_once()


def test_pr_open_failure_falls_back_to_dm(orchestrator_components, tmp_path):
    """If PROpener.open raises, the orchestrator falls back to DM-with-could_not_verify."""
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.return_value = ClaudeOutcome(
        outcome="pr_ready", reasoning="r",
        files_changed=["docs/x.md"], commit_sha="abc",
        verified_against=["liferay-portal:y"],
    )
    pr_opener.open.side_effect = RuntimeError("github 503")
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="x",
    )
    orch.handle(Event(channel="C1", message_ts="t", reactor_user="U",
                      message_text="m", permalink="p"))
    pr_opener.open.assert_called_once()
    dm_sender.send.assert_called_once()
    kwargs = dm_sender.send.call_args.kwargs
    assert kwargs["outcome"] == "could_not_verify"
    assert "github 503" in kwargs["reasoning"]


def test_prompt_template_tolerates_braces_in_message(orchestrator_components):
    """The orchestrator must not crash on Slack messages containing { or },
    which str.format would mishandle but Template.safe_substitute tolerates."""
    pool, claude, pr_opener, dm_sender, slack = orchestrator_components
    claude.run.return_value = ClaudeOutcome(
        outcome="no_change_needed", reasoning="r",
        files_changed=[], commit_sha="", verified_against=[],
    )
    orch = Orchestrator(
        pool=pool, claude=claude, pr_opener=pr_opener, dm_sender=dm_sender,
        slack_client=slack,
        processing_emoji="p", done_emoji="d",
        prompt_template="msg=${message_text} url=${permalink}",
    )
    orch.handle(Event(
        channel="C1", message_ts="t", reactor_user="U",
        message_text="java method foo({}, bar) returns {x: 1}",
        permalink="https://slack/p",
    ))
    # Claude was called with a prompt that includes the braces verbatim.
    prompt_arg = claude.run.call_args.kwargs.get("prompt") or claude.run.call_args.args[1]
    assert "java method foo({}, bar)" in prompt_arg
    assert "https://slack/p" in prompt_arg
