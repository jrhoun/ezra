import os
from pathlib import Path

import pytest

from docbot.config import load_config, ConfigError


VALID_CONFIG = (
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


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_env_var_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "secret-123")
    cfg = load_config(write_yaml(tmp_path, VALID_CONFIG))
    assert cfg.slack.bot_token == "secret-123"
    assert cfg.slack.app_token == "secret-123"


def test_missing_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
    cfg_path = write_yaml(tmp_path, "slack:\n  bot_token: ${DOES_NOT_EXIST}\n")
    with pytest.raises(ConfigError, match="DOES_NOT_EXIST"):
        load_config(cfg_path)


def test_missing_required_key(tmp_path, monkeypatch):
    monkeypatch.setenv("T", "x")
    cfg_path = write_yaml(tmp_path, "slack:\n  bot_token: ${T}\n")
    with pytest.raises(ConfigError, match="watch_channel_id"):
        load_config(cfg_path)


def test_substitution_in_list_element(tmp_path, monkeypatch):
    """Env var substitution must recurse into list values, not just leaf strings."""
    monkeypatch.setenv("MY_TOKEN", "tok")
    monkeypatch.setenv("REPO_ONE", "liferay/liferay-portal")
    yaml_with_list_sub = VALID_CONFIG.replace(
        "  verification_repos: []\n",
        "  verification_repos:\n    - ${REPO_ONE}\n",
    )
    cfg = load_config(write_yaml(tmp_path, yaml_with_list_sub))
    assert cfg.repos.verification_repos == ["liferay/liferay-portal"]


def test_config_root_must_be_mapping(tmp_path):
    """A YAML file whose root is not a mapping is rejected with a clear error."""
    cfg_path = write_yaml(tmp_path, "- a\n- b\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(cfg_path)


def test_unexpected_key_raises(tmp_path, monkeypatch):
    """A typo'd YAML key under a known section surfaces as ConfigError, not a bare TypeError."""
    monkeypatch.setenv("MY_TOKEN", "tok")
    yaml_with_typo = VALID_CONFIG.replace(
        "  bot_token: ${MY_TOKEN}\n",
        "  bot_token: ${MY_TOKEN}\n  bot_tokken: extra\n",
    )
    with pytest.raises(ConfigError, match="bot_tokken"):
        load_config(write_yaml(tmp_path, yaml_with_typo))


def test_example_yaml_loads_with_env_vars_stubbed(monkeypatch, tmp_path):
    """The shipped config.example.yaml must round-trip cleanly through load_config
    with the env vars it references set to stub values. Guards against future
    config additions that quietly break the example."""
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-stub")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-stub")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C-STUB")
    example = Path(__file__).resolve().parents[2] / "config.example.yaml"
    assert example.exists(), f"Expected example at {example}"
    cfg = load_config(example)
    # Sanity checks; we don't pin every value, just confirm the load worked
    # and key dataclass fields are populated.
    assert cfg.slack.app_token == "xapp-stub"
    assert cfg.github.upstream_repo == "liferay/liferay-learn"
    assert cfg.mode.dry_run is False
    assert isinstance(cfg.claude.allowed_tools, list)
