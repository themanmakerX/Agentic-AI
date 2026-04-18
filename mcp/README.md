# MCP

This directory contains the repository's MCP packages and plugins.

## Included packages

- [`knowledge-graph/`](knowledge-graph/) - Python MCP package for persistent code graph indexing, graph queries, workspace analysis, architecture exploration, and a FastAPI web UI.
- [`vault/`](vault/) - MCP plugin bundle for persistent agent memory, vault selection, records, facts, links, journals, hooks, and checkpoint workflows.

## When to use each package

- Use `knowledge-graph` when you need structural understanding of a repository, dependency exploration, architecture summaries, or retrieval-backed graph queries.
- Use `vault` when you need durable memory across sessions, structured facts, links, checkpoints, and searchable saved context.

## Layout

```text
mcp/
|- knowledge-graph/
|- vault/
`- README.md
```

## Maintenance note

If a package is renamed, added, or removed, update this README together with the package README so the index remains accurate.
