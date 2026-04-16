# code-review-graph

`code-review-graph` is a Python package for building a codebase graph and exposing it through MCP-oriented tooling.

This worker added the CLI shell and TOML installer support:

- `crg install` merges an MCP server entry into `config.toml`
- `crg build`, `crg update`, `crg status`, and `crg serve` remain available from the main CLI
- `python -m code_review_graph` now works from the repo root

## Quick start

```bash
pip install -e .
crg install --config config.toml
crg serve
```

## Docs

- `docs/cli.md`
- `docs/config.toml.md`

## MCP Setup

Add this to your Codex `config.toml`:

```toml
[mcp_servers.code-review-graph]
command = "python"
args = ["-m", "code_review_graph_mcp.server", "--root", "E:/Education/code-review-graph"]
cwd = "E:/Education/code-review-graph/src"

[mcp_servers.code-review-graph.env]
PYTHONPATH = "E:/Education/code-review-graph/src"
```

This launches the MCP server from the `src/` package root so the server imports resolve correctly on Windows.
