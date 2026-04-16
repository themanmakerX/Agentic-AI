# Output Format

## Objective

Generate a repo instruction tree that is easy to navigate, conservative by default, and explicit about scope boundaries.

## Required Deliverables

### 1. Root Instruction File

The root file must contain:

- repo purpose
- repository layout
- command entrypoints
- global conventions
- generated/excluded paths
- child-doc index
- open questions or assumptions when needed

### 2. Nested Instruction Files

Each nested file must contain:

- the local scope it owns
- why the scope exists
- local commands or workflows
- local rules or invariants
- parent reference
- child reference list if needed
- out-of-scope note

### 3. Scope Report

Before or after writing docs, produce a short scope report with:

- scope name
- owned paths
- evidence used
- commands discovered
- excluded paths
- uncertainties
- follow-up agent passes required, if any

## Schema

Use this shape for the generated plan:

```json
{
  "repo": "<repo-name>",
  "source_of_truth": "<AGENTS.md-or-CLAUDE.md>",
  "scopes": [
    {
      "path": ".",
      "doc": "<root-instruction-file>",
      "owned_paths": ["<child-scope>"],
      "commands": ["<discovered-command-entrypoint>"],
      "rules": ["<root-rule>"],
      "children": ["<child-scope>/<instruction-file>"],
      "evidence": ["<evidence-file>"],
      "uncertainties": []
    }
  ]
}
```

## Writing Constraints

- Prefer real paths and real commands over placeholders.
- Mark assumptions explicitly.
- Keep the root scope as the navigation hub.
- Keep nested scopes minimal and local.
- Do not duplicate the same rule at multiple levels unless required for clarity.
