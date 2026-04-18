# Agentic-AI

Agentic-AI is a repository of reusable assets for coding agents. It combines two complementary layers:

- `skills/` for agent behavior, workflows, prompts, and packaged skill bundles
- `mcp/` for MCP servers and plugins that provide graph analysis, memory, and related tooling

The repository is organized so that instruction-driven workflows and executable tooling can evolve side by side while still being easy to discover.

## Repository areas

### Skills

The [`skills/`](skills/) directory contains the repository's skill packages:

- [`repo-onboarding/`](skills/repo-onboarding/) for repository analysis, context building, and onboarding workflows
- [`superdeveloper/`](skills/superdeveloper/) for a larger multi-agent bundle with platform-specific integrations, commands, tests, docs, hooks, and embedded MCP references

See [skills/README.md](E:/Education/Agentic-AI/skills/README.md) for the skills index.

### MCP

The [`mcp/`](mcp/) directory contains the repository's MCP packages and plugins:

- [`knowledge-graph/`](mcp/knowledge-graph/) for persistent code graph indexing, querying, architecture exploration, and a browser-based graph UI
- [`vault/`](mcp/vault/) for persistent agent memory, vault selection, records, facts, links, journals, and checkpoint workflows

See [mcp/README.md](E:/Education/Agentic-AI/mcp/README.md) for the MCP index.

## Layout

```text
Agentic-AI/
|- mcp/
|  |- knowledge-graph/
|  `- vault/
|- skills/
|  |- repo-onboarding/
|  `- superdeveloper/
`- README.md
```

## How to navigate this repo

- Start in `skills/` if you want reusable agent instructions or workflow guidance.
- Start in `mcp/` if you want runnable tooling that agents can call through MCP.
- Open `skills/superdeveloper/` if you want the most complete packaged bundle in the repository.
- Open `mcp/knowledge-graph/` if you want codebase indexing and graph exploration.
- Open `mcp/vault/` if you want persistent memory and checkpoint storage.

## Documentation expectations

This repository depends heavily on discoverability. When folders, commands, or capabilities change:

- update the nearest README first
- keep parent index READMEs aligned with actual folder names
- remove stale package names and outdated install paths
- prefer concise indexes at the top level and deeper operational detail near the implementation
