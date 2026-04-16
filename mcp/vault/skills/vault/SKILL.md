---
name: vault
description: Use when the user wants persistent local memory, a vault location, or to search, store, journal, or switch vaults.
---

# Vault

Use Vault when the task needs persistent local memory for Codex or Claude Code.

## Operating rules

1. If no active vault exists, ask the user for a vault location.
2. If the user already has one or more vaults, present the saved options and continue in the selected vault.
3. Prefer the active vault automatically on later turns.
4. Use `vault_add_record`, `vault_journal_write`, `vault_add_fact`, and `vault_add_link` to persist relevant work.
5. Use `vault_search`, `vault_query_entity`, and `vault_status` before guessing about saved context.

## When to use

- First-run setup
- Switching between personal and work vaults
- Saving decisions, snippets, and checkpoints
- Looking up past context
- Maintaining a persistent project memory
