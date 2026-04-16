# CLI Reference

The package exposes two command names:

- `crg`
- `code-review-graph`

## `install`

Writes an MCP server entry into a TOML config file.

Example:

```bash
crg install --config config.toml
```

Defaults:

- config file: `config.toml`
- server name: `code-review-graph`
- launcher: `code-review-graph`
- launcher args: `["serve"]`
- working directory: the current folder
- top-level section: `mcp`

## `build`

Builds a full local graph for the target repository.

```bash
crg build --root .
```

## `update`

Updates only files whose content hash changed.

```bash
crg update --root .
```

## `status`

Prints SQLite-backed graph statistics.

## `serve`

Runs the MCP server against the local graph database.

## Useful install flags

- `--section`: override the top-level TOML section
- `--arg`: append extra launcher arguments
- `--launcher`: override the executable used to start the server
- `--env`: add environment variables as `KEY=VALUE`
- `--dry-run`: print the merged TOML without writing it
- `--no-backup`: skip the `.bak` backup file
