---
name: repo-onboarding
description: Deep repository onboarding and instruction-tree generation. Use when analyzing an unfamiliar codebase, mapping its directory structure, spawning subagents to inspect each level or domain, and creating or refreshing hierarchical AGENTS.md/CLAUDE.md guidance with validation against the real tree.
---

# Repo Onboarding

## Core Workflow

1. Run a structured repository scan.
2. Map the repository tree from the root downward.
3. Identify the repo's own source of truth for agent instructions.
4. Ask the user which instruction-file convention to generate.
   - Use the embedded AskUserQuestion tool.
   - Default choices should be: `auto`, `Codex` (`CLAUDE.md`), or `Claude` (`AGENTS.md`).
5. Split the tree into meaningful ownership zones.
6. Spawn subagents for each independent zone.
7. Synthesize one root instruction file plus nested files for each boundary.
8. Re-scan the tree and verify the instructions cover what actually exists.

## Automation-First Flow

Use the bundled scanner before writing anything:

```bash
python scripts/scan_repo.py --root <repo-path> --json
```

Use the scan output to drive:

- top-level scope identification
- nested scope boundaries
- existing instruction-file reuse
- command discovery
- exclusion of generated/vendor paths
- instruction-file convention selection

## Generation Mode

- `auto`: follow the repository's existing convention when one is present.
- `claude`: generate `CLAUDE.md` files.
- `codex`: generate `AGENTS.md` files.

If the convention is not explicit, ask the user before writing files.
If files already exist and would be replaced, back them up first into a dedicated backup directory before writing the new version.

## Operating Rules

- Prefer the repository's existing instruction name and convention.
  - If the repo uses `CLAUDE.md`, keep `CLAUDE.md` as authoritative.
  - If the repo uses `AGENTS.md`, keep `AGENTS.md` as authoritative.
  - If both exist, follow the repo's current convention and avoid duplicating conflicting guidance.
- Support both initial onboarding and maintenance mode.
  - Onboarding: create the first instruction tree from scratch.
  - Maintenance: refresh existing instruction files when the repo changes.
- Be conservative by default.
  - If a boundary is ambiguous, keep the scope in the parent file.
  - If evidence is weak, record an uncertainty instead of inventing a rule.
  - If a folder looks important but has no unique behavior, do not split it.
- Treat generated, vendor, lockfile, and third-party directories as excluded unless they contain repo-owned behavior.
- Keep root guidance broad and stable.
- Keep nested guidance local, specific, and short.
- Split large subtrees by responsibility, not just by folder depth.
- Record assumptions when the tree does not fully explain ownership or workflow.
- Stop splitting when another level would only repeat the parent with no new commands, rules, or ownership.
- Prefer evidence over inference when a rule is not directly supported by files, tasks, or docs.

## Analysis Sequence

### 1. Discover

Inspect:

- repository layout
- build and task entrypoints
- language/runtime boundaries
- test and validation commands
- existing instruction files
- generated and excluded paths

If code-review graph data or code-review MCP is available, use it to accelerate relationship discovery, then confirm the results against the filesystem.
When available, also inspect task, build, and CI entrypoints before inventing any command guidance.
Prefer the scanner output over ad hoc directory walking when both are available.

### 2. Partition

Create a scope map with:

- root scope
- top-level domains
- nested domains that need their own guidance
- shared libraries and cross-cutting layers
- generated or read-only areas

Stop splitting when a scope no longer changes commands, rules, or ownership.
Keep an explicit list of what is intentionally undocumented, especially for vendor and generated trees.

### 3. Delegate

Spawn focused agents instead of one broad agent.

Recommended roles:

- tree scout: summarize the directory structure and candidate boundaries
- domain scout: inspect one top-level domain per agent
- dependency scout: identify shared modules and cross-links
- doc writer: draft the root and nested instruction files
- verifier: compare draft instructions with the real tree and flag gaps

Give each agent a narrow prompt, a single scope, and a precise output format:

- owned paths
- responsibilities
- local commands
- special rules
- dependencies
- documentation gaps

Ask at least one verifier pass after drafting so missing folders, conflicting rules, and stale assumptions can be caught before you finish.

### 4. Synthesize

Write instructions in layers:

- root file: repo-wide conventions, commands, architecture, safety rules, and links to child docs
- nested files: local commands, invariants, ownership, and exceptions that only apply inside that subtree
- sibling files: use when one folder contains distinct concerns that should not share a single large document

Keep the docs factual. Do not invent commands or architecture that was not observed.
Prefer explicit links between parent and child docs so the hierarchy is discoverable in either direction.
Use the formal output schema in [output-format.md](references/output-format.md) when drafting or refreshing the instruction tree.

### 5. Validate

Run one final pass against the actual tree:

- confirm every important folder has a home
- confirm excluded folders are not documented as owned code
- confirm nested docs point back to the parent scope
- confirm there are no conflicting rules between levels
- confirm the root file still reads as the single entry point
- confirm any task runner, build tool, or CI command mentioned in docs still exists
- confirm any stated dependency or layering rule is visible in the tree or supporting config

If anything is missing, send a second targeted agent pass before finalizing.

## Output Schema

Follow the repository instruction tree schema in [output-format.md](references/output-format.md).

## Bundled Resources

- [scan_repo.py](scripts/scan_repo.py) - deterministic repository scanner and scope candidate generator
- [write_instruction_drafts.py](scripts/write_instruction_drafts.py) - draft writer for generated AGENTS/CLAUDE files
- [tree-analysis.md](references/tree-analysis.md) - scope splitting rules and agent roles
- [instruction-templates.md](references/instruction-templates.md) - root and nested doc templates
- [validation-checklist.md](references/validation-checklist.md) - final pass checklist
- [output-format.md](references/output-format.md) - formal output schema for generated docs
