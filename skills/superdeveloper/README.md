# Superdeveloper

Superdeveloper is a packaged multi-agent skill bundle for coding assistants. It combines reusable skills with platform integrations, hooks, commands, tests, bundled MCP references, and supporting documentation.

## What is included

- `skills/` for reusable SKILL-based workflows
- `agents/` for specialized agent personas and reviewer roles
- `commands/` for higher-level command entry points
- `docs/` for installation notes, usage guides, design docs, and plans
- `hooks/` for runtime hook configuration and helper scripts
- `mcp/` for bundled MCP references used by the package
- `tests/` for skill-triggering, integration, and platform-specific validation
- platform folders such as `.codex/`, `.claude-plugin/`, `.cursor-plugin/`, and `.opencode/`

## Main workflow areas

The bundle includes skills for:

- brainstorming and planning
- subagent-driven development
- systematic debugging
- code review request/response flows
- repo onboarding
- test-driven development
- verification before completion
- using git worktrees

See [skills/README.md](E:/Education/Agentic-AI/skills/superdeveloper/skills/README.md) for the skill index.

## MCP references

The embedded [`mcp/`](mcp/) folder currently contains:

- `code-review-graph/`
- `vault/`

See [mcp/README.md](E:/Education/Agentic-AI/skills/superdeveloper/mcp/README.md) for the MCP overview inside this bundle.

## Docs and installation entry points

- [docs/README.codex.md](E:/Education/Agentic-AI/skills/superdeveloper/docs/README.codex.md) for Codex-oriented setup
- [docs/README.opencode.md](E:/Education/Agentic-AI/skills/superdeveloper/docs/README.opencode.md) for OpenCode-oriented setup
- `CLAUDE.md` and `GEMINI.md` for platform-specific companion docs

## Layout

```text
skills/superdeveloper/
|- agents/
|- commands/
|- docs/
|- hooks/
|- mcp/
|- skills/
|- tests/
|- CLAUDE.md
|- GEMINI.md
`- README.md
```

## Maintenance note

This package contains several nested indexes. When you add, rename, or remove workflows, update the nearest README and any parent index that references it.
