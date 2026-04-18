# Superdeveloper for OpenCode

Guide for using the `superdeveloper` bundle with [OpenCode.ai](https://opencode.ai).

## Installation

Add the repository plugin reference to your `opencode.json`:

```json
{
  "plugin": ["superdeveloper@git+https://github.com/themanmakerX/Agentic-AI.git"]
}
```

Restart OpenCode after updating the config.

## What this package provides

The `superdeveloper` bundle includes:

- a packaged skill set under `skills/superdeveloper/skills/`
- OpenCode plugin wiring under `skills/superdeveloper/.opencode/`
- docs, tests, commands, hooks, and supporting assets around those skills

## Skill discovery

Use OpenCode's native skill tooling to inspect and load package skills. A typical path inside this bundle is:

```text
superdeveloper/<skill-name>
```

Examples:

- `superdeveloper/brainstorming`
- `superdeveloper/systematic-debugging`
- `superdeveloper/subagent-driven-development`

## Updating

Because the plugin points at the Git repository, restarting OpenCode refreshes the installed bundle from the repo reference you configured.

## Related docs

- Main package overview: `skills/superdeveloper/README.md`
- Codex install guide: `skills/superdeveloper/docs/README.codex.md`
