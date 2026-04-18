# DEVELOPER.md Template

This is a reference template for projects that use `superdeveloper` and need a maintenance guide.

## Purpose

Describe the orchestration design clearly enough for future contributors to extend it safely.

## Suggested Sections

- System overview
- Platform detection strategy
- Phase and gate model
- Agent roles and responsibilities
- Documentation workflow
- Verification strategy
- Failure handling and fallback behavior
- Extension points

## Example Content Pattern

- **Architecture**: explain how the orchestrator routes work across phases and agents.
- **Contracts**: list the rules that must not be broken.
- **Tests**: show what validates the orchestration behavior.
- **Decision log**: capture important tradeoffs and rejected approaches.
- **Maintenance**: explain where to change the workflow and how to avoid regressions.

## Writing Rules

- Be precise about behavior, not aspirational.
- State gates, thresholds, and responsibilities explicitly.
- Document the expected inputs and outputs of each phase.
- Keep the guide aligned with the actual skill behavior.
