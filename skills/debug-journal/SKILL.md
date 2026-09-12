---
name: debug-journal
description: Create, update, and search structured, integrity-checked debug journals for design verification (DV) bug hunts — RTL, testbench, sequence, spec, tool, and infra bugs. Use whenever the user asks to log a bug, start a debug journal, record a hypothesis/root cause, confirm or retract a diagnosis, reopen a closed bug, record a fix (files + line numbers), flag a regression, search/rank similar past bugs, get stats or a digest, or bulk-import a spreadsheet/Jira export of past bugs. Always consult this skill for verification debug tracking or "have we seen this before" questions, even without the word "journal."
---

# Debug Journal

A layered, integrity-checked system for logging DV bug hunts from first symptom to confirmed fix — designed so two people (or two CLI invocations) running this at once can't corrupt each other's data, and so future bugs can be matched against past ones with real path/signature normalization instead of naive substring matching.

## Architecture

```
CLI / Skill Layer      create.js, update.js, search.js, stats.js, digest.js,
                        interactive.js, import.js, rebuild-index.js
        │
Validation Layer        lib/schema.js  — field validation (titles, lines, severity, dates)
                        lib/fsm.js     — diagnosis/workflow lifecycle state machine
        │
   ┌────┼────────────────────┬─────────────────────┐
   ▼                         ▼                      ▼
Journal Service         Similarity Engine       Log Parser
lib/journal-service.js  lib/similarity.js       lib/log-parser.js
(create/update/import,  (ranked "have we seen   (streaming, gzip-aware,
 collision-safe ids,     this before" scoring,    multi-pattern failure
 regression/relation-    path+signature aware)    detection, dedup)
 ship validation)
   │                         │                      │
   └─────────────────────────┼──────────────────────┘
                             ▼
                    Persistence Layer
              lib/atomic.js (atomic writes)
              lib/lock.js   (owner-token file lock, dead-owner recovery)
              lib/journal-store.js (transactional JSON+MD I/O, schema migration)
              lib/index-service.js (locked transaction, structural/stale auto-rebuild)
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
           journals/*.json         index.json
                  │
                  └── generated ──► *.md
```

Every journal has two representations, kept in sync automatically:
- `journals/<id>.json` — canonical, queryable data (schema-versioned, auto-migrated)
- `journals/<id>.md` — human-readable rendering, generated from the JSON

`index.json` is a flat rollup for fast search/ranking. If it's corrupted, structurally invalid, stale, or deleted, read paths rebuild it automatically from `journals/*.json`; rebuild refuses to write a partial index if any canonical journal is unreadable; you can also do it explicitly with `rebuild-index.js`.

## Lifecycle model (schema v3)

Diagnosis and closure are separate dimensions:

- `status`: `investigating` → `predicted` → `confirmed`, or `retracted`.
- `workflow_state`: `OPEN` or `CLOSED`.

`confirmed` and `retracted` automatically close the workflow. An `investigating`/`predicted` journal may also be closed with `--resolution` for outcomes such as `duplicate`, `not-a-bug`, or `wont-fix` without lying about the diagnosis. Any change to a CLOSED journal requires `--reopen`. Reopen starts a new current investigation cycle: top-level `date_predicted`/`date_confirmed`/`date_closed` are reset appropriately while full prior history remains in `status_history`.

All calendar dates are strict Gregorian `YYYY-MM-DD` (so impossible dates such as `2026-02-31` are rejected), and current-day generation uses the machine's local calendar date rather than UTC.

## Category & severity

Category: `rtl` · `testbench` · `sequence` · `spec` · `tool` · `infra`
Severity: `blocker` · `major` (default) · `minor`

## IMPORTANT: check before creating

```bash
node scripts/search.js --suggest --symptom "<what you observed>" --tags <tags> \
  --file <touched file, if known> --lines <line range, if known> \
  --failure-signature "<log line/assertion, if known>"
```
This ranks past journals by tag overlap, category match, **path-normalized** fix-file/line overlap (so `rtl\foo.sv` and `./rtl/foo.sv` correctly match the same file — no more false positives from bare substring matching), **normalized failure-signature** match (ignores timestamps/hex/seed noise), and text similarity. If a strong match comes back, use `--regression-of <that id>` on create instead of logging fresh.

## Workflow

### 1. Create
```bash
node scripts/create.js --title "AXI write hang under back-to-back bursts" \
  --category rtl --severity blocker \
  --test-name tb_axi_wr --seed 84213 \
  --failure-signature "UVM_ERROR: timeout waiting for BVALID @ 1230ns" \
  --symptom "Write channel hangs after 3rd back-to-back burst" \
  --tags axi,hang,fsm
```
IDs are collision-safe: a duplicate title/date gets `-2`, `-3`, etc. — never silently overwritten. Optional: `--regression-of <id>`, `--evidence-log/--evidence-waveform/--evidence-note` (repeatable), `--from-log <path>` (streams a log, gzip-aware, recognizes `UVM_ERROR`/`UVM_FATAL`/`$fatal`/`TEST_FAILED`/assertion failures/Xcelium `*E,` errors, dedupes repeats), `--date-opened` for backdating.

Prefer `node scripts/interactive.js` over remembering flags — same validated path underneath.

### 2. Hypothesis → confirm
```bash
node scripts/update.js --id <id> --status predicted --hypothesis "..."

node scripts/update.js --id <id> --status confirmed \
  --root-cause "..." --fix-description "..." \
  --fix-file "rtl/axi_wr_fsm.sv|142-158|added deassert" \
  --fix-commit a1b2c3d --owner atif
```
`--fix-file` format: `path|lines|note` (lines/note optional, repeatable). Invalid line specs (reversed, zero, negative, malformed) are rejected with a clear error before anything is written.

### 3. Search / rank / rollups
```bash
node scripts/search.js --tag axi
node scripts/search.js --file rtl/axi_wr_fsm.sv --lines 150-160   # path-normalized overlap
node scripts/search.js --text "back-to-back burst"
node scripts/search.js --regression
node scripts/stats.js              # category/status/severity, avg time-to-confirm, hot files, reopen count
node scripts/digest.js --days 7 [--write]
```

### 4. Bulk import
```bash
node scripts/import.js --file past_bugs.csv --dry-run
node scripts/import.js --file past_bugs.csv
```
Handles UTF-8 BOM, required/unknown-column reporting, mismatched-column-count rows, duplicate-row detection (content fingerprint, checked against both the CSV and existing journals), historical `date_opened`/`date_confirmed`/`date_closed` columns (validated for chronology — a row claiming it was confirmed before it was opened is rejected), and drive-letter-safe `path:lines` parsing for `fix_files` (so `C:\repo\foo.sv:10-20` parses correctly instead of splitting on the drive-letter colon). Use `;` inside a cell for multiple tags/fix files.

### 5. Recovery
```bash
node scripts/rebuild-index.js   # manual rebuild; also runs automatically if index.json is ever corrupted
```

## What this hardening pass actually closes

Built against a specific bug list (duplicate/overwritten journals, invalid lifecycle transitions, non-atomic/racy writes, lock ownership/stale-lock races, Windows path bugs, impossible dates, reopen chronology, dangling/circular regression references, schema migration/version guards, stale/invalid index recovery, false-positive path matching, log-parser memory/format limits, CSV import date/duplicate/encoding issues). All of the above was verified with targeted tests (collision under concurrent creation, invalid transition rejection + audit trail on reopen, circular regression detection, corrupted-index auto-rebuild, drive-letter path parsing, gzip log parsing with pattern dedup, CSV BOM + historical dates + chronology validation + duplicate-row detection).

## Known limitations (not attempted, or only partially covered)

- **Stale line numbers**: a fix recorded at `rtl/foo.sv:142-158` will drift if the file is edited afterward — nothing here tracks source history to keep it current.
- **Semantic/NLP duplicate detection**: CSV import and `--suggest` catch exact/near-exact repeats (fingerprint or normalized-signature match), not bugs that are the same root cause described in very different words.
- **Signature/log-format coverage**: `normalizeSignature`/`extractComponentPath`/`extractAssertionId` and the log-parser's failure patterns are heuristic regexes tuned for common UVM/Xcelium/VCS conventions, not a full parser for every simulator's log grammar — expect gaps on unusual formats.
- **Locking is single-machine only**: ownership-token locks protect concurrent processes on one machine and never evict a live owner based only on elapsed time. They are not a distributed lock for multiple hosts sharing a network filesystem.
