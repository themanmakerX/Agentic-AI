# Skills

This directory contains the repository's skill packages and skill bundles.

## Included packages

- [`debug-journal/`](debug-journal/) - Structured, integrity-checked DV debug journals with bug lifecycle tracking, similarity search, regression links, stats, digests, and CSV import.
- [`ledger/`](ledger/) - Local-first, append-only developer session ledger with audit integrity, checkpoints, replay, search, summaries, hooks, and a lightweight dashboard.
- [`repo-onboarding/`](repo-onboarding/) - Repository onboarding skill for codebase analysis, context building, and instruction-tree generation.
- [`superdeveloper/`](superdeveloper/) - Full multi-agent skill bundle with platform integrations, commands, docs, hooks, MCP references, tests, and reusable development workflows.

## How to use this directory

- Open `debug-journal/` for verification debug tracking and "have we seen this before" bug-history workflows.
- Open `ledger/` for local session logging, command/file replay, checkpoints, and audit summaries.
- Open `repo-onboarding/` for focused repository understanding workflows.
- Open `superdeveloper/` for the larger packaged system that includes multiple skills, commands, docs, and integrations.

## Layout

```text
skills/
|- debug-journal/
|- ledger/
|- repo-onboarding/
|- superdeveloper/
`- README.md
```

## Maintenance note

Keep this index aligned with the actual folder names and avoid README entries that point to paths that no longer exist.
