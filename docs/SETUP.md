# Setup

## Requirements

- Python 3.10 or newer
- An MCP client that can launch a local server process
- A graph backend implementation that conforms to `GraphBackend`

## Install

From the repository root:

```bash
pip install -e .
```

If you use `uv`, the equivalent flow is:

```bash
uv sync
uv run code-review-graph
```

## Start the server

```bash
code-review-graph
```

The current package ships a working MCP server backed by the local SQLite graph.
If the backend cannot be initialized, tools will still fail with a clear `MissingBackendError`.

## Production wiring

Before production use, connect the MCP layer to the graph core implementation by passing a backend instance into `create_server()`.

The backend must implement the shared contract in `src/code_review_graph_mcp/contracts.py`.
