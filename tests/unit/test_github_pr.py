from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docbot.github.pr import PROpener, PRRequest


def test_dry_run_writes_to_log(tmp_path, monkeypatch):
    log_dir = tmp_path / "dry-run"
    opener = PROpener(
        fork_owner="jrhoun",
        upstream_repo="liferay/liferay-learn",
        base_branch="master",
        pr_label="docs/slack-bot",
        pr_title_prefix="",
        dry_run=True,
        dry_run_dir=log_dir,
    )
    req = PRRequest(
        workdir=tmp_path,
        branch="docbot/1234-fix",
        title_subject="Fix LPS-X reference",
        body="some body",
    )
    url = opener.open(req)
    files = list(log_dir.iterdir())
    assert len(files) == 1
    assert "docbot/1234-fix" in url


def test_live_invokes_git_push_and_gh(tmp_path, mocker):
    run_mock = mocker.patch("docbot.github.pr.subprocess.run")
    run_mock.return_value = MagicMock(stdout="https://github.com/liferay/liferay-learn/pull/42\n", returncode=0)

    opener = PROpener(
        fork_owner="jrhoun",
        upstream_repo="liferay/liferay-learn",
        base_branch="master",
        pr_label="docs/slack-bot",
        pr_title_prefix="",
        dry_run=False,
        dry_run_dir=tmp_path,
    )
    req = PRRequest(workdir=tmp_path, branch="docbot/b", title_subject="t", body="b")
    url = opener.open(req)
    assert url == "https://github.com/liferay/liferay-learn/pull/42"

    # First call: git push to jrhoun fork
    push_call = run_mock.call_args_list[0]
    assert push_call[0][0][0:2] == ["git", "push"]
    assert "jrhoun" in push_call[0][0][2]

    # Second call: gh pr create
    gh_call = run_mock.call_args_list[1]
    assert gh_call[0][0][0:3] == ["gh", "pr", "create"]
