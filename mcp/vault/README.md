# Vault

Vault is an MCP plugin for persistent agent memory, vault selection, records, facts, links, journals, and checkpoint hooks.

## What it stores

- records for notes, decisions, snippets, and context
- facts for structured entity relationships
- links for explicit record-to-record connections
- journal entries for session checkpoints and handoff notes

## Core behavior

- uses one active vault at a time
- prompts once when no vault is configured
- remembers the chosen vault location
- supports multiple vaults and switching between them
- exposes optional hooks for automatic checkpointing

## Package files

- `./.mcp.json` exposes the MCP server
- `./hooks.json` wires optional client hooks
- `./scripts/` contains the runtime and CLI helpers
- `./skills/vault/SKILL.md` provides the operating rules for assistants
- `./.codex-plugin/plugin.json` contains plugin metadata

## Default storage

Vault data lives under `~/.vault` by default.

Each vault directory gets its own `.vault/` metadata folder.

## Typical use cases

- carry context across sessions
- save explicit decisions and checkpoints
- store structured facts that can be queried later
- keep multiple named vaults for different projects or domains
