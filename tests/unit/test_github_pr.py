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


import json
from docbot.github.pr import PRError


def test_dry_run_json_content(tmp_path):
    """Dry-run JSON file contains all expected keys with correct values."""
    log_dir = tmp_path / "dry-run"
    opener = PROpener(
        fork_owner="jrhoun",
        upstream_repo="liferay/liferay-learn",
        base_branch="master",
        pr_label="docs/slack-bot",
        pr_title_prefix="[bot]",
        dry_run=True,
        dry_run_dir=log_dir,
    )
    req = PRRequest(workdir=tmp_path, branch="docbot/123-x", title_subject="Subject", body="Body")
    opener.open(req)
    files = list(log_dir.iterdir())
    payload = json.loads(files[0].read_text())
    assert payload["branch"] == "docbot/123-x"
    assert payload["title"] == "[bot] Subject"
    assert payload["body"] == "Body"
    assert payload["label"] == "docs/slack-bot"
    assert payload["fork_owner"] == "jrhoun"
    assert payload["upstream_repo"] == "liferay/liferay-learn"


def test_git_push_failure_raises_structured_error(tmp_path, mocker):
    """git push returning non-zero raises PRError with kind='push_failed'
    and preserves returncode + stderr."""
    run_mock = mocker.patch("docbot.github.pr.subprocess.run")
    run_mock.return_value = MagicMock(stdout="", stderr="permission denied", returncode=128)
    opener = PROpener(
        fork_owner="jrhoun", upstream_repo="liferay/liferay-learn",
        base_branch="master", pr_label="docs/slack-bot", pr_title_prefix="",
        dry_run=False, dry_run_dir=tmp_path,
    )
    req = PRRequest(workdir=tmp_path, branch="docbot/x", title_subject="t", body="b")
    with pytest.raises(PRError) as excinfo:
        opener.open(req)
    err = excinfo.value
    assert err.kind == "push_failed"
    assert err.returncode == 128
    assert "permission denied" in (err.stderr or "")


def test_gh_create_failure_raises_structured_error(tmp_path, mocker):
    """gh pr create returning non-zero raises PRError with kind='gh_create_failed'.
    The git push call must succeed before gh is invoked."""
    run_mock = mocker.patch("docbot.github.pr.subprocess.run")
    # First call: git push succeeds; second call: gh pr create fails.
    run_mock.side_effect = [
        MagicMock(stdout="", stderr="", returncode=0),
        MagicMock(stdout="", stderr="label not found", returncode=1),
    ]
    opener = PROpener(
        fork_owner="jrhoun", upstream_repo="liferay/liferay-learn",
        base_branch="master", pr_label="missing-label", pr_title_prefix="",
        dry_run=False, dry_run_dir=tmp_path,
    )
    req = PRRequest(workdir=tmp_path, branch="docbot/x", title_subject="t", body="b")
    with pytest.raises(PRError) as excinfo:
        opener.open(req)
    err = excinfo.value
    assert err.kind == "gh_create_failed"
    assert err.returncode == 1
    assert "label not found" in (err.stderr or "")


def test_fork_remote_override(tmp_path, mocker):
    """fork_remote parameter overrides the default '<fork_owner>-fork' convention."""
    run_mock = mocker.patch("docbot.github.pr.subprocess.run")
    run_mock.return_value = MagicMock(stdout="https://github.com/x/y/pull/1\n", returncode=0)
    opener = PROpener(
        fork_owner="jrhoun", upstream_repo="liferay/liferay-learn",
        base_branch="master", pr_label="docs/slack-bot", pr_title_prefix="",
        dry_run=False, dry_run_dir=tmp_path,
        fork_remote="origin",
    )
    req = PRRequest(workdir=tmp_path, branch="docbot/x", title_subject="t", body="b")
    opener.open(req)
    push_call = run_mock.call_args_list[0]
    # git push <fork_remote> <branch> — third positional arg should be "origin"
    assert push_call[0][0][2] == "origin"
