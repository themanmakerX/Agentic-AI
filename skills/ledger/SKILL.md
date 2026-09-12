# Session Ledger v3

A local-first, append-only developer activity ledger for AI/code sessions. No Git or GitHub integration is included.

## Architecture

- `events.jsonl`: authoritative append-only, SHA-256 hash-chained journal.
- `ledger.json` / `ledger.md`: human/machine derived views.
- `summary.json`: automatic session summary.
- `ledger-index.sqlite`: optional local FTS5 search/index layer on Node 22+ (`node:sqlite`). JSONL remains authoritative.
- `checkpoints/`: file-level safety snapshots for risky operations.
- `policy.json`: local policy, redaction, checkpoint, and retention settings.

## Integrated capabilities

### Reliability and audit integrity
- atomic metadata/index/view writes
- durable append (`fsync`) for events
- owner-aware session/index locks
- hash chain and sequential event verification
- corruption refusal/recovery tooling
- safe legacy migration
- ended-session write rejection
- path-traversal-safe session IDs

### Efficiency
- append-only primary storage
- SQLite FTS5 index for fast full-text search
- index rebuild command
- transparent gzip archive of ended journals (source journal is compressed, not duplicated)
- retention policy support, including max-session archival
- bounded detail payloads

### Intelligence
- language detection
- symbol extraction (SystemVerilog/Verilog, Python, JS/TS, C/C++, Rust, Perl, Tcl)
- dependency/include/import extraction
- change classification
- risk scoring
- test/build command classification (`pytest`, `make`, VCS, Xrun, Questa, TRS, etc.)
- test outcome classification (`PASS`, `FAIL`, `TIMEOUT`)
- automatic FAIL → change(s) → PASS correlation
- same-file and change→test causal relations in SQLite
- session-level file dependency graph from includes/imports
- parent/child session metadata and tree view
- event parent/causal metadata
- natural-language `ask` evidence search (local FTS/token evidence; no external model required)

### Safety
- pre-persistence secret redaction
- sensitive-path content redaction
- automatic checkpoint for high-risk operations in Claude pre-hooks
- manual checkpoint/list/restore with dry-run
- configurable local policy

### Human workflow
- automatic session summary
- chronological replay
- command/file replay filters
- lightweight local web dashboard (`scripts/dashboard.js`)

## CLI

```bash
node scripts/cli.js start-session --client claude-code --project my_project --cwd /work
node scripts/cli.js start-session --parent <parent-session-id>
node scripts/cli.js log --op edit --tool Edit --path file.sv --summary "fix reset" --detail "..."
node scripts/cli.js summary --session <id>
node scripts/cli.js replay --session <id>
node scripts/cli.js replay --commands --session <id>
node scripts/cli.js graph --session <id>
node scripts/cli.js tree
node scripts/cli.js relations --session <id>
node scripts/cli.js correlations --session <id>
node scripts/cli.js search scoreboard --session <id>
node scripts/cli.js ask "what changed in reset scoreboard" --session <id>
node scripts/cli.js checkpoint --path file1.sv,file2.py --session <id>
node scripts/cli.js checkpoints --session <id>
node scripts/cli.js restore <checkpoint-id> --session <id> --dry-run
node scripts/cli.js restore <checkpoint-id> --session <id>
node scripts/cli.js policy
node scripts/cli.js policy --set='{"checkpointRiskAtOrAbove":4}'
node scripts/cli.js reindex
node scripts/cli.js repair --session <id>
node scripts/cli.js end-session --session <id>
node scripts/cli.js archive --session <id>
node scripts/cli.js retention
```

Dashboard:

```bash
LEDGER_PORT=8766 node scripts/dashboard.js
```

Then open `http://127.0.0.1:8766`.

## Claude Code hook

Use `scripts/hooks/claude-code-hook.js` for both `PreToolUse` and `PostToolUse`. Pre-hooks capture the pre-state and create risk-triggered checkpoints. Post-hooks append the normalized event.

Captured tool families include Read/View, Write/Create, Edit/StrReplace, NotebookEdit, Delete/Remove, Rename/Move and Bash.

## Generic hook

`scripts/hooks/generic-hook.js` accepts normalized JSON on stdin. Required: `session_id`, `op`, `tool`; non-Bash operations also require `path`.

## Policy defaults

Generated automatically at `$LEDGER_HOME/policy.json`:
- redact secrets before persistence
- redact sensitive file content (`.env`, keys, credentials/secrets paths)
- checkpoint risk score >= 4
- archive ended sessions after configured retention age or session-count threshold

## Important limitation

Bash is captured at command level. A shell command or arbitrary program may mutate files internally; the ledger cannot infer every filesystem side effect unless the client emits those file operations separately. File-level checkpoint restore only restores files explicitly snapshotted; it is not a full filesystem transaction/VM snapshot.
