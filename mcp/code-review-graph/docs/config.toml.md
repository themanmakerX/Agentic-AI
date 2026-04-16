# `config.toml` Integration

The installer merges a single MCP server entry into a TOML document without removing unrelated top-level data.

## Default shape

```toml
[mcp.servers.code-review-graph]
command = "code-review-graph"
args = ["serve"]
cwd = "mcp/code-review-graph"
```

## Customization

You can override the target section and the launch details:

```bash
crg install \
  --config ./config.toml \
  --section mcp \
  --name code_review_graph \
  --launcher python \
  --arg serve \
  --cwd .
```

Environment variables are stored as a nested TOML table:

```bash
crg install --env CRG_LOG_LEVEL=debug --env CRG_WORKSPACE=/tmp/project
```

which produces:

```toml
[mcp.servers.code_review_graph.env]
CRG_LOG_LEVEL = "debug"
CRG_WORKSPACE = "/tmp/project"
```

## Merge rules

- Existing unrelated data is preserved.
- If the target server key already exists, it is replaced by default.
- `--dry-run` prints the full merged TOML to stdout without writing a file.
- A backup file is created before writing unless `--no-backup` is used.
- `--cwd` is resolved to an absolute path before writing.
- The default server command is `code-review-graph`.
