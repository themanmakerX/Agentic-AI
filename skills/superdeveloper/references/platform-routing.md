# Platform Routing

Use the active environment to decide which native behavior to follow.

## Detection Heuristics

- `CLAUDE_PLUGIN_ROOT` or `AGENTS.md` context: Claude Code-style behavior.
- `OPENCODE_CONFIG_DIR` or the OpenCode plugin path: OpenCode-style behavior.
- `CODEX_CI`, Codex CLI config, or native Codex tool availability: Codex-style behavior.
- `CURSOR_PLUGIN_ROOT`: Cursor-style behavior.
- `GEMINI.md` context: Gemini-style behavior.
- If none are obvious: use the generic skill flow and keep the gates intact.

## Tool Adaptation

Map the skill's actions to the platform's native tools.

- Codex: `spawn_agent`, `wait_agent`, `close_agent`, `update_plan`, shell tools.
- Claude Code: `Skill`, `Task`, `TodoWrite`, hooks, and plugin metadata.
- OpenCode: native `skill` tool, plugin config hooks, and the platform's file tools.
- Cursor: cursor hook bootstrap plus its own execution model.
- Gemini: `activate_skill`, `write_todos`, `read_file`, `run_shell_command`.

## Behavior Rules

- Prefer native multi-agent support when the platform has it.
- If the platform cannot do parallel agents, degrade to a single-agent sequential flow.
- If a platform has a finishing limitation, stop at the best safe handoff and document the limitation.
- Keep platform-specific workarounds out of the main skill body unless they affect the operating order.
