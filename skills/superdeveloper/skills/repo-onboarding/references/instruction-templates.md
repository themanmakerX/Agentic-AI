# Instruction Templates

## Root Instruction File

Use the root file as the repo entry point.

Include:

- repo purpose
- high-level architecture
- directory map
- canonical setup, build, test, and validation commands
- global coding rules
- generated files and forbidden edits
- a short "how to navigate this repo" note for future agents
- links to nested instruction files

Keep it short enough to stay readable at a glance.

```md
# <Repo Name>

This file is the source of truth for working in this repository.

## Layout

- `<top-level-scope>/` - ...
- `<top-level-scope>/` - ...
- `<top-level-scope>/` - ...

## Common Commands

- `<repo-entrypoint-command>`
- `<repo-entrypoint-command>`

## Global Rules

- ...

## Nested Guides

- [<child-scope>/<instruction-file>](<child-scope>/<instruction-file>)
- [<child-scope>/<instruction-file>](<child-scope>/<instruction-file>)
```

## Nested Instruction File

Use nested files for a subtree, package, or domain.

Include:

- local commands
- domain-specific conventions
- local generated files
- import or dependency limits
- exceptions that only apply inside that subtree
- a short parent reference
- a short note on what this file intentionally does not cover

```md
# <Child Scope>

This file covers `<child-scope>/` only.
Follow the root file for repo-wide rules.

## Local Commands

- ...

## Local Rules

- ...
```

## Split Criteria

Create another nested file when one folder contains separate concerns, for example:

- one subtree has different command entrypoints from its sibling
- one subtree has distinct ownership or runtime behavior
- one subtree needs special policy or dependency rules
- one subtree would make the parent too broad if absorbed

## Writing Rules

- Write only what the codebase proves.
- Prefer concrete commands and paths over abstractions.
- Point to children instead of repeating the same rule in every level.
- Keep each file authoritative for its own scope.
- If a command is optional or environment-specific, mark it as such.
- If a rule is inferred, label it as an inference or add it to the uncertainty list.
