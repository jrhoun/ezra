"""docbot CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from slack_sdk import WebClient

from docbot.claude_runner.runner import ClaudeRunner
from docbot.config import load_config
from docbot.github.pr import PROpener
from docbot.logging_setup import configure_logging
from docbot.orchestrator.orchestrator import Orchestrator
from docbot.refresher import RepoRefresher
from docbot.slack.dm import DMSender
from docbot.slack.listener import build_app
from docbot.worktree.pool import WorktreePool


DEFAULT_PROMPT = """\
Investigate this Liferay documentation report by running the
/verify-doc-report skill. The skill defines the verification methodology
and output format.

Slack message:
${message_text}

Slack permalink: ${permalink}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()

    configure_logging(level=logging.INFO)
    log = logging.getLogger("docbot")

    cfg = load_config(args.config)

    base_repo_path = Path(cfg.repos.root) / Path(cfg.repos.base_repo).name
    pool = WorktreePool(
        base_repo=base_repo_path,
        root=Path(cfg.repos.root) / "worktrees",
        size=cfg.worktree.pool_size,
    )
    pool.start()

    claude = ClaudeRunner(
        binary=cfg.claude.binary,
        timeout_sec=cfg.claude.timeout_sec,
        max_turns=cfg.claude.max_turns,
        allowed_tools=cfg.claude.allowed_tools,
    )

    dry_run_dir = Path("./dry-run-output")
    pr_opener = PROpener(
        fork_owner=cfg.github.fork_owner,
        upstream_repo=cfg.github.upstream_repo,
        base_branch=cfg.github.base_branch,
        pr_label=cfg.github.pr_label,
        pr_title_prefix=cfg.github.pr_title_prefix,
        dry_run=cfg.mode.dry_run,
        dry_run_dir=dry_run_dir / "prs",
    )

    slack_client = WebClient(token=cfg.slack.bot_token)
    dm_sender = DMSender(
        client=None if cfg.mode.dry_run else slack_client,
        default_user=cfg.slack.dm_default_user,
        dry_run=cfg.mode.dry_run,
        dry_run_dir=dry_run_dir / "dms",
    )

    orchestrator = Orchestrator(
        pool=pool,
        claude=claude,
        pr_opener=pr_opener,
        dm_sender=dm_sender,
        slack_client=slack_client,
        processing_emoji=cfg.slack.processing_emoji,
        done_emoji=cfg.slack.done_emoji,
        prompt_template=DEFAULT_PROMPT,
    )

    refresher_repos = [
        Path(cfg.repos.root) / Path(r).name for r in cfg.repos.verification_repos
    ]
    refresher = RepoRefresher(
        repos=refresher_repos,
        interval_sec=cfg.repos.refresh_interval_hours * 3600,
    )
    refresher.start()

    handler = build_app(
        bot_token=cfg.slack.bot_token,
        app_token=cfg.slack.app_token,
        watch_channel_id=cfg.slack.watch_channel_id,
        trigger_emoji=cfg.slack.trigger_emoji,
        max_message_age_days=cfg.worktree.max_message_age_days,
        orchestrator=orchestrator,
    )

    log.info("docbot starting", extra={"dry_run": cfg.mode.dry_run})
    try:
        handler.start()
    except KeyboardInterrupt:
        pass
    finally:
        refresher.stop()
        pool.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
