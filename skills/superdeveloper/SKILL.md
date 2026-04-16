---
name: superdeveloper
description: End-to-end development orchestration with automatic platform detection, staged multi-agent teams, devil's-advocate review, continuous documentation capture, and final README, usage manual, and developer manual generation. Use when starting or managing coding work, feature work, bug fixes, refactors, or multi-step implementation that should adapt automatically to Codex, Claude Code, OpenCode, Cursor, or Gemini.
---

# Superdeveloper

Use this skill as the top-level orchestrator for development work.

## Hard Rules

- Detect the active platform before any implementation decision.
- Preserve the native behavior of the active platform instead of forcing a generic flow.
- Create a fresh phase team for each phase.
- Keep the documentation agent active from first decision to final handoff.
- Trigger the devil's advocate only after the phase clears its local quality gate.
- Do not claim completion until verification, review, and documentation are all finished.

## Operating Order

1. Detect the active platform and adopt its native behavior. See [platform-routing.md](references/platform-routing.md).
2. Classify scope, risk, and whether the task needs a lightweight or full-team flow.
3. Break the work into phases with explicit gates. See [phase-teams.md](references/phase-teams.md).
4. For every phase, run a small team:
   - lead
   - builder
   - reviewer
   - documentation agent
   - devil's advocate after the phase clears its local quality gate
5. Keep the documentation agent active from the beginning to the end.
6. Prefer existing superdeveloper skills instead of re-creating their logic.
7. Finish only after verification, review, and documentation output are complete.

## Team Policy

- Use the smallest team that can still reach a defensible answer.
- Expand the team only when risk, ambiguity, or breadth makes the smaller team insufficient.
- Make the lead responsible for scope control and gate decisions.
- Make the builder responsible for the smallest correct change.
- Make the reviewer responsible for defects, regressions, and spec drift.
- Make the devil's advocate responsible for breaking the proposed solution after the local gate is met.
- Make the documentation agent responsible for a complete running ledger, not just a final summary.

## Required Skill Chain

Use the existing superdeveloper skills in this order when applicable:

- `superdeveloper:using-superdeveloper` for bootstrap and skill discipline
- `superdeveloper:brainstorming` for discovery and design
- `superdeveloper:writing-plans` for task decomposition
- `superdeveloper:using-git-worktrees` for workspace isolation
- `superdeveloper:subagent-driven-development` when subagents are available
- `superdeveloper:executing-plans` when subagents are unavailable
- `superdeveloper:systematic-debugging` for failures and regressions
- `superdeveloper:requesting-code-review` and `superdeveloper:receiving-code-review` for review loops
- `superdeveloper:verification-before-completion` before any success claim
- `superdeveloper:finishing-a-development-branch` for the final handoff

## Platform Adaptation

Follow the active platform's native tools and constraints instead of forcing one harness model onto another. Read [platform-routing.md](references/platform-routing.md) before starting if the environment is not obvious.

- Codex: use native multi-agent primitives, read-only git checks, and Codex tool equivalents.
- Claude Code: use Skill and Task-based flows, hooks, and the plugin metadata already provided by the repo.
- OpenCode: use the plugin hook path and the native `skill` tool mapping.
- Cursor: use the Cursor hook manifest and plugin behavior.
- Gemini: use `GEMINI.md` and the Gemini tool mapping.
- Unknown or partial support: degrade to a single-agent flow and keep the same gates.

## Phase Teams

Create a new team for each phase. Keep the team small, focused, and isolated.

- **Lead**: owns the phase output and decides whether the gate is met.
- **Builder**: produces the artifact or code.
- **Reviewer**: checks correctness, scope fit, and regressions.
- **Devil's advocate**: challenges assumptions only after the phase clears its local gate.
- **Documentation agent**: records decisions, tradeoffs, open risks, and final artifacts throughout the work.

See [phase-teams.md](references/phase-teams.md) for the phase matrix and quality gates.

## Documentation

Never treat documentation as an afterthought. The documentation agent must keep a running ledger from the first decision onward and finish by producing the project's README, usage manual, and developer manual. See [documentation-pipeline.md](references/documentation-pipeline.md).

At minimum, end-state documentation should cover:

- what the project does
- how to use it
- how the architecture and workflow fit together
- what was decided, what was rejected, and why

## Quality Gates

Do not advance a phase until its gate is met.

- Discovery gate: scope, constraints, success criteria, and platform are clear.
- Design gate: architecture, tradeoffs, and boundaries are explicit.
- Plan gate: files, tasks, tests, and order of work are concrete.
- Build gate: the implementation matches the plan and does not add unrelated scope.
- Verify gate: the observed behavior matches the claim.
- Review gate: no critical or important defects remain.
- Documentation gate: ledger plus README, usage manual, and developer manual are complete and consistent.

## Devil's Advocate

Activate the devil's advocate only after the phase is locally good enough. Its job is to break assumptions, expose missing edge cases, and force a stronger threshold before the work is accepted.

- Look for silent failure modes.
- Look for scope creep.
- Look for brittle platform assumptions.
- Look for gaps between the plan, the implementation, and the docs.

## Fallback Mode

If the platform cannot run a full multi-agent team, keep the same phase order and quality gates in a single-agent flow. Do not skip the documentation agent; fold its work into the same session and final handoff.

## Final Output

The final handoff should include:

- the completed work
- verification evidence
- open risks or caveats
- README.md
- usage manual
- developer manual

If the user asks for broader documentation, extend the ledger into an architecture note or decision log, but do not drop the three required docs.
