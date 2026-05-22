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


def test_runner_nonzero_exit(tmp_path):
    """A non-zero exit from claude raises ClaudeError with kind='exit' and
    surfaces the returncode + stderr for the orchestrator to log."""
    failing = tmp_path / "fail-claude"
    failing.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'something went wrong' >&2\n"
        "exit 2\n"
    )
    failing.chmod(0o755)
    runner = ClaudeRunner(binary=str(failing), timeout_sec=30, max_turns=10, allowed_tools=[])
    with pytest.raises(ClaudeError) as excinfo:
        runner.run(workdir=tmp_path, prompt="x")
    err = excinfo.value
    assert err.kind == "exit"
    assert err.returncode == 2
    assert "something went wrong" in (err.stderr or "")


def test_runner_passes_max_turns_and_allowed_tools(tmp_path, monkeypatch):
    """The runner must pass --max-turns and --allowed-tools through to the CLI."""
    capture_script = tmp_path / "capture-claude"
    # Write argv to a file the test can inspect, then emit a valid JSON outcome.
    capture_script.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$ARGS_PATH\"\n"
        "echo '{\"outcome\": \"no_change_needed\", \"reasoning\": \"x\", "
        "\"files_changed\": [], \"commit_sha\": \"\", \"verified_against\": []}'\n"
    )
    capture_script.chmod(0o755)
    args_path = tmp_path / "args.txt"
    monkeypatch.setenv("ARGS_PATH", str(args_path))
    runner = ClaudeRunner(
        binary=str(capture_script),
        timeout_sec=30,
        max_turns=42,
        allowed_tools=["Read", "Bash(git:*)"],
    )
    outcome = runner.run(workdir=tmp_path, prompt="hello prompt")
    assert outcome.outcome == "no_change_needed"
    args = args_path.read_text().splitlines()
    # Order is preserved by the implementation: [-p prompt --max-turns 42 --allowed-tools Read --allowed-tools Bash(git:*)]
    assert args[0] == "-p"
    assert args[1] == "hello prompt"
    assert "--max-turns" in args
    assert "42" in args
    # Both allowed-tools should be passed individually.
    assert args.count("--allowed-tools") == 2
    assert "Read" in args
    assert "Bash(git:*)" in args
