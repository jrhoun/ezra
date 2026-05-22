# docs-slack-pr-bot

A Slack-driven bot that converts `#documentation` channel reports into verified PRs against a target documentation repository.

The bot's verification methodology is defined in a user-invocable skill in the target docs repo, not in this codebase. The bot is a generic conduit: Slack input → spawn Claude with the skill → push branch + open PR on success, or DM the trigger user on failure. All site-specific values live in `config.yaml`.

See `config.example.yaml` for the configuration surface.

## Status

Pre-alpha. Phase 2 of a four-phase rollout — see the spec.

## License

Apache-2.0.
