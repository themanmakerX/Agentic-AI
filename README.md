# Agentic-AI

Agentic-AI is a multi-agent ecosystem for coding agents. This repository is split into two main parts:

- `skills/` for agent behavior, workflows, and instruction files
- `mcp/code-review-graph/` for the MCP-powered code review graph service

The goal of the repo is to make agent workflows more structured, more reviewable, and easier to use across different client platforms.

## What is inside

### Skills

The `skills/` tree contains the agent-facing workflows that get triggered during coding sessions. The current skill index includes:

- `repo-onboarding` - deep repository onboarding, tree analysis, and instruction-tree generation
- `superdeveloper` - end-to-end development orchestration with platform detection, staged multi-agent teams, review gates, and documentation capture

See [`skills/README.md`](skills/README.md) for the skill index.

### MCP tooling

The `mcp/code-review-graph/` tree contains a standalone Python package that builds a repository graph and exposes it through MCP-oriented tooling.

It provides:

- graph build and update commands
- MCP server startup support
- TOML install helpers for client configuration
- workspace analysis, review context, semantic search, and graph stats

See [`mcp/code-review-graph/README.md`](mcp/code-review-graph/README.md) for the MCP package details.

## Repository layout

```text
Agentic-AI/
├─ mcp/
│  └─ code-review-graph/
├─ skills/
└─ README.md
```

## How to use this repo

- If you want to add or inspect agent workflows, start in `skills/`
- If you want to run or extend the code review graph service, start in `mcp/code-review-graph/`
- If you are onboarding to the repository, read `skills/repo-onboarding/SKILL.md`
- If you want the multi-agent orchestration workflow, read `skills/superdeveloper/SKILL.md`

## Why it is structured this way

The repository separates agent instructions from service code so each part can evolve independently:

- skills can focus on agent behavior and workflow guidance
- the MCP package can focus on code analysis and review tooling
- the root README can stay short and point people to the right place quickly

## Contributing

When changing a skill, keep the skill index up to date and make sure the documentation matches the actual folder structure.

When changing the MCP package, keep the package README and `pyproject.toml` aligned with the code and install flow.
