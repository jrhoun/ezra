"""Investigation orchestrator: ties the components into a pipeline."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from slack_sdk import WebClient

from docbot.claude_runner.runner import ClaudeRunner, ClaudeError, ClaudeOutcome
from docbot.github.pr import PROpener, PRRequest
from docbot.slack.dm import DMSender
from docbot.slack.reactions import claim_message, mark_done
from docbot.worktree.pool import WorktreePool, NoWorktreeAvailable

log = logging.getLogger(__name__)


@dataclass
class Event:
    channel: str
    message_ts: str
    reactor_user: str
    message_text: str
    permalink: str


def _slug(text: str, max_len: int = 30) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len] or "report"


class Orchestrator:
    def __init__(
        self,
        pool: WorktreePool,
        claude: ClaudeRunner,
        pr_opener: PROpener,
        dm_sender: DMSender,
        slack_client: WebClient,
        processing_emoji: str,
        done_emoji: str,
        prompt_template: str,
    ) -> None:
        self.pool = pool
        self.claude = claude
        self.pr_opener = pr_opener
        self.dm_sender = dm_sender
        self.slack = slack_client
        self.processing_emoji = processing_emoji
        self.done_emoji = done_emoji
        self.prompt_template = prompt_template

    def handle(self, event: Event) -> None:
        # 1. Claim by adding processing emoji. If already_reacted, drop.
        claimed = claim_message(
            self.slack, channel=event.channel, ts=event.message_ts,
            emoji=self.processing_emoji,
        )
        if not claimed:
            log.info("event already claimed", extra={"ts": event.message_ts})
            return

        # 2. Claim a worktree.
        try:
            wt = self.pool.claim(branch_slug=_slug(event.message_text))
        except NoWorktreeAvailable:
            log.warning("pool exhausted", extra={"ts": event.message_ts})
            self._dm_failure(event, "Bot is busy — please retry in a few minutes.", [])
            mark_done(self.slack, event.channel, event.message_ts,
                      self.processing_emoji, self.done_emoji)
            return

        try:
            # 3. Run claude.
            prompt = self.prompt_template.format(
                message_text=event.message_text,
                permalink=event.permalink,
            )
            try:
                outcome = self.claude.run(workdir=wt.path, prompt=prompt)
            except ClaudeError as e:
                log.warning("claude failed", extra={"err": str(e), "ts": event.message_ts})
                self._dm_failure(event, f"Investigation failed: {e}", [])
                return

            # 4. Dispatch.
            if outcome.outcome == "pr_ready":
                self._handle_pr_ready(event, wt, outcome)
            else:
                self.dm_sender.send(
                    reactor_user=event.reactor_user,
                    outcome=outcome.outcome,
                    reasoning=outcome.reasoning,
                    permalink=event.permalink,
                    verified_against=outcome.verified_against,
                )
        finally:
            self.pool.release(wt)
            mark_done(self.slack, event.channel, event.message_ts,
                      self.processing_emoji, self.done_emoji)

    def _handle_pr_ready(self, event: Event, wt, outcome: ClaudeOutcome) -> None:
        body = self._render_pr_body(event, outcome)
        title_subject = outcome.reasoning.split(".")[0][:70] or "Doc fix from Slack report"
        req = PRRequest(
            workdir=wt.path,
            branch=wt.branch,
            title_subject=title_subject,
            body=body,
        )
        try:
            url = self.pr_opener.open(req)
            log.info("pr opened", extra={"url": url, "ts": event.message_ts})
        except Exception as e:
            log.exception("pr open failed")
            self.dm_sender.send(
                reactor_user=event.reactor_user,
                outcome="could_not_verify",
                reasoning=f"Investigation produced a diff but PR creation failed: {e}",
                permalink=event.permalink,
                verified_against=outcome.verified_against,
            )

    def _dm_failure(self, event: Event, reasoning: str, verified_against: list[str]) -> None:
        self.dm_sender.send(
            reactor_user=event.reactor_user,
            outcome="could_not_verify",
            reasoning=reasoning,
            permalink=event.permalink,
            verified_against=verified_against,
        )

    @staticmethod
    def _render_pr_body(event: Event, outcome: ClaudeOutcome) -> str:
        lines = [
            "## Source report",
            "",
            "> " + event.message_text.replace("\n", "\n> "),
            "",
            f"Slack permalink: {event.permalink}",
            "",
            "## Investigation summary",
            "",
            outcome.reasoning,
            "",
            "## Verified against",
            "",
        ]
        for v in outcome.verified_against:
            lines.append(f"- `{v}`")
        return "\n".join(lines)
