# Phase Teams

Use a fresh team for each phase. Reuse the same phase order, but not the same assumptions.

## Phase Matrix

| Phase | Lead output | Builder output | Reviewer focus | Devil's advocate trigger |
|---|---|---|---|---|
| Discovery | clear problem framing | notes, constraints, alternatives | completeness and ambiguity | after scope and success criteria are explicit |
| Design | design summary | architecture options | tradeoffs and fit | after architecture and boundaries are set |
| Planning | task plan | file-by-file breakdown | order, granularity, testability | after tasks are concrete |
| Implementation | code changes | minimal working edits | correctness and regressions | after the implementation matches the plan |
| Verification | test results | verification commands and logs | evidence quality | after the claim is supported by output |
| Review | review notes | fix list | severity and correctness | after low-risk issues are cleared |
| Documentation | running ledger | README, usage manual, developer manual | completeness and consistency | after the three docs are drafted |
| Finish | handoff summary | branch/PR/cleanup decision | final state and cleanup | after all prior gates are green |

## Team Composition

Use the smallest team that can still produce a defensible result.

- **Low risk**: lead + builder + reviewer
- **Medium risk**: lead + builder + reviewer + documentation agent
- **High risk**: lead + builder + reviewer + documentation agent + devil's advocate

## Threshold Rules

- Do not start the devil's advocate until the phase has a usable local result.
- If the reviewer finds a real gap, fix it before the devil's advocate pass.
- If the devil's advocate finds a real gap, revise the phase output and re-run the reviewer.
- If a phase keeps failing, reduce scope before increasing agent count.

## Documentation Agent Behavior

- Record the decision, rationale, and follow-up for every phase.
- Keep the ledger concise, factual, and chronological.
- Carry forward unresolved risks into the next phase.
- Use the ledger to generate the final docs at the end.
