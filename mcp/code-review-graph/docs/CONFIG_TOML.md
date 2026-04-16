# `config.toml` Integration

This project is designed to be launched from a long-lived client config.

## Example

```toml
[mcp.servers.code-review-graph]
command = "code-review-graph"
args = ["serve"]
cwd = "mcp/code-review-graph"
env = { PYTHONUTF8 = "1" }
```

## Notes

- Use the absolute path of the workspace you want the graph server to analyze.
- Keep the command stable so every client session starts the same server.
- If your MCP host uses a different table name, keep the same values and adapt the table header to match that host.
- The installer writes the entry under the configured section and preserves unrelated TOML data.

## Common variations

If your environment needs an explicit Python launcher:

```toml
[mcp.servers.code-review-graph]
command = "python"
args = ["-m", "code_review_graph_mcp.server"]
cwd = "mcp/code-review-graph"
```

If you later add a backend-specific environment variable, include it in the same `env` table.
