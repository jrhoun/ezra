"""Configuration loader: YAML + env var substitution."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    pass


_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match) -> str:
            name = m.group(1)
            if name not in os.environ:
                raise ConfigError(f"Env var ${{{name}}} referenced in config but not set")
            return os.environ[name]
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _substitute(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v) for v in value]
    return value


@dataclass
class SlackConfig:
    app_token: str
    bot_token: str
    watch_channel_id: str
    trigger_emoji: str
    processing_emoji: str
    done_emoji: str
    dm_default_user: str | None = None


@dataclass
class GitHubConfig:
    fork_owner: str
    upstream_repo: str
    base_branch: str
    pr_label: str
    pr_title_prefix: str


@dataclass
class ClaudeConfig:
    binary: str
    max_turns: int
    timeout_sec: int
    allowed_tools: list[str] = field(default_factory=list)


@dataclass
class ReposConfig:
    root: str
    refresh_interval_hours: int
    base_repo: str
    verification_repos: list[str] = field(default_factory=list)


@dataclass
class WorktreeConfig:
    pool_size: int
    max_message_age_days: int


@dataclass
class ModeConfig:
    dry_run: bool


@dataclass
class Config:
    slack: SlackConfig
    github: GitHubConfig
    claude: ClaudeConfig
    repos: ReposConfig
    worktree: WorktreeConfig
    mode: ModeConfig


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(raw).__name__}")
    raw = _substitute(raw)
    try:
        return Config(
            slack=SlackConfig(**raw["slack"]),
            github=GitHubConfig(**raw["github"]),
            claude=ClaudeConfig(**raw["claude"]),
            repos=ReposConfig(**raw["repos"]),
            worktree=WorktreeConfig(**raw["worktree"]),
            mode=ModeConfig(**raw["mode"]),
        )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Missing or invalid config key: {e}") from e
