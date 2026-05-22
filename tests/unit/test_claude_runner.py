import json
from pathlib import Path

import pytest

from docbot.claude_runner.runner import ClaudeRunner, ClaudeOutcome, ClaudeError


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    """A fake claude CLI that echoes a controllable JSON outcome."""
    script = tmp_path / "fake-claude"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "# Reads $FAKE_PRELUDE and $FAKE_JSON and emits them.\n"
        "echo \"$FAKE_PRELUDE\"\n"
        "echo \"$FAKE_JSON\"\n"
    )
    script.chmod(0o755)
    return script


def test_runner_parses_last_json_line(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PRELUDE", "some chatter\nmore chatter")
    monkeypatch.setenv(
        "FAKE_JSON",
        json.dumps({
            "outcome": "pr_ready",
            "reasoning": "the flag was promoted",
            "files_changed": ["docs/foo.md"],
            "commit_sha": "abc123",
            "verified_against": ["liferay-portal:feature.flag.foo"],
        }),
    )
    runner = ClaudeRunner(binary=str(fake_claude), timeout_sec=30, max_turns=10, allowed_tools=[])
    outcome = runner.run(workdir=tmp_path, prompt="investigate")
    assert outcome.outcome == "pr_ready"
    assert outcome.commit_sha == "abc123"
    assert outcome.files_changed == ["docs/foo.md"]


def test_runner_timeout(tmp_path):
    slow = tmp_path / "slow-claude"
    slow.write_text("#!/usr/bin/env bash\nsleep 10\n")
    slow.chmod(0o755)
    runner = ClaudeRunner(binary=str(slow), timeout_sec=1, max_turns=10, allowed_tools=[])
    with pytest.raises(ClaudeError, match="timeout"):
        runner.run(workdir=tmp_path, prompt="x")


def test_runner_malformed_output(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PRELUDE", "not json")
    monkeypatch.setenv("FAKE_JSON", "also not json")
    runner = ClaudeRunner(binary=str(fake_claude), timeout_sec=30, max_turns=10, allowed_tools=[])
    with pytest.raises(ClaudeError, match="unparseable"):
        runner.run(workdir=tmp_path, prompt="x")
