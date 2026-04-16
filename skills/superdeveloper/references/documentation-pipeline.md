# Documentation Pipeline

The documentation agent is always active. It records decisions continuously and turns the final work into project docs.

## Running Ledger

Keep a short ledger while the work is in progress.

- phase
- date or session marker
- decision
- rationale
- rejected alternative
- risk or follow-up

## Final Docs

Generate these three files at the end of the work:

1. `README.md`
   - what the project does
   - what problem it solves
   - quick start
   - key workflow or architecture summary

2. `USAGE.md`
   - commands or invocation patterns
   - examples
   - common scenarios
   - platform-specific notes if needed

3. `DEVELOPER.md`
   - architecture
   - agent flow
   - quality gates
   - extension points
   - tests and verification expectations

If the repository also carries reference templates, keep them under `docs/superdeveloper/` and align them with the final docs contract.

## Optional Additions

If the project needs more depth, add:

- `ARCHITECTURE.md`
- `DECISIONS.md`
- `CHANGELOG.md`

Only add these when they help the project. Do not create extra docs by default.

## Consistency Rules

- The final docs must agree with the implementation and the ledger.
- The README must stay concise and user-facing.
- The usage manual must be operational.
- The developer manual must explain the system clearly enough for future maintenance.
