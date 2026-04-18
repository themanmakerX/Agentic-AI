# Configuration

Code Review Graph supports installation into a `config.toml` file that contains MCP server definitions.

## Recommended Install

```bash
code-review-graph install --config path/to/config.toml
```

## Resulting TOML Shape

```toml
[mcp.servers.code-review-graph]
command = "python"
args = ["-m", "code_review_graph.server"]
cwd = "/absolute/path/to/your/repo"
```

## Notes

- The installer creates a backup before writing.
- Existing `mcp.servers` entries are preserved.
- You can override the server name, command, args, and working directory from the CLI.
- If you pass `--root` to the server and omit `--db`, the database defaults to `.code-review-graph/graph.sqlite3` under that root.
- The `install` command resolves `cwd` to an absolute path so the generated config stays stable across shells.
