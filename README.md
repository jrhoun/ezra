# ezra

A Slack-driven bot that converts `#documentation` channel reports into verified PRs against a target documentation repository. Named for the Old Testament scribe who returned to Jerusalem to verify and teach the law — same role, smaller scale.

The bot's verification methodology is defined in a user-invocable skill in the target docs repo, not in this codebase. ezra is a generic conduit: Slack input → spawn Claude with the skill → push branch + open PR on success, or DM the trigger user on failure. All site-specific values live in `config.yaml`.

See `config.example.yaml` for the configuration surface.

## Implementation note

The internal Python package is named `docbot` (from earlier scaffolding). It is imported as `from docbot.* import ...` throughout the codebase. The repository, the installed CLI binary, and user-facing references use `ezra`.

## Status

Pre-alpha. Phase 2 of a four-phase rollout — see the spec.

## License

Apache-2.0.
