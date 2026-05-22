import os
import tempfile
from pathlib import Path
import pytest

from docbot.config import load_config, ConfigError


def write_yaml(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_env_var_substitution(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "secret-123")
    cfg_path = write_yaml(
        "slack:\n"
        "  bot_token: ${MY_TOKEN}\n"
        "  watch_channel_id: C123\n"
        "  trigger_emoji: robot_face\n"
        "  processing_emoji: docbot-thinking\n"
        "  done_emoji: docbot-done\n"
        "  app_token: ${MY_TOKEN}\n"
        "github:\n"
        "  fork_owner: jrhoun\n"
        "  upstream_repo: liferay/liferay-learn\n"
        "  base_branch: master\n"
        "  pr_label: docs/slack-bot\n"
        "  pr_title_prefix: ''\n"
        "claude:\n"
        "  binary: /usr/local/bin/claude\n"
        "  max_turns: 30\n"
        "  timeout_sec: 900\n"
        "  allowed_tools: []\n"
        "repos:\n"
        "  root: /tmp/repos\n"
        "  refresh_interval_hours: 4\n"
        "  base_repo: liferay/liferay-learn\n"
        "  verification_repos: []\n"
        "worktree:\n"
        "  pool_size: 3\n"
        "  max_message_age_days: 30\n"
        "mode:\n"
        "  dry_run: true\n"
    )
    cfg = load_config(cfg_path)
    assert cfg.slack.bot_token == "secret-123"
    assert cfg.slack.app_token == "secret-123"


def test_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
    cfg_path = write_yaml("slack:\n  bot_token: ${DOES_NOT_EXIST}\n")
    with pytest.raises(ConfigError, match="DOES_NOT_EXIST"):
        load_config(cfg_path)


def test_missing_required_key(monkeypatch):
    monkeypatch.setenv("T", "x")
    cfg_path = write_yaml(
        "slack:\n  bot_token: ${T}\n"
        # Missing watch_channel_id and others
    )
    with pytest.raises(ConfigError, match="watch_channel_id"):
        load_config(cfg_path)
