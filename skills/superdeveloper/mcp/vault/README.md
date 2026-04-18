# Vault

Vault is an MCP plugin for persistent agent memory, vault selection, record storage, facts, links, journals, and checkpoint hooks.

## What it stores

- Records: verbatim notes, decisions, snippets, and context
- Facts: structured entity relationships with optional validity windows
- Links: explicit connections between records
- Journal entries: session checkpoints and handoff notes

## Core behavior

- Uses one active vault at a time
- Prompts once when no vault is configured
- Remembers the chosen vault location
- Supports multiple vaults and switching between them
- Offers optional hooks for automatic checkpointing

## Files

- `./.mcp.json` exposes the MCP server
- `./hooks.json` wires optional Claude Code hooks
- `./scripts/` contains the server and CLI helpers
- `./skills/vault/SKILL.md` gives the agent the operating rules

## Default storage

Vault data lives under `~/.vault` by default.

Each vault directory gets its own `.vault/` metadata folder.

## How the assistant should behave

- If there is no active vault, ask the user for a vault location
- If the user already has vaults, show the existing options and continue from the selected one
- Keep writing checkpoints and records over time
- Use the active vault automatically after it is configured
