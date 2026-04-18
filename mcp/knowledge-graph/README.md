# knowledge-graph

`knowledge-graph` is a persistent code graph service with three surfaces:

- MCP tools for Codex and other agents
- a FastAPI web app for interactive graph browsing
- a shared indexing/query backend used by both

## Requirements

- Python 3.10+
- `fastapi`
- `uvicorn`
- `mcp`
- an installed `knowledge-graph` launcher, for example from:

```bash
pip install -e .
```

## Layout

```text
app/
src/knowledge_graph/
|- graph/
|- mcp/
|- backend.py
|- cli.py
|- jobs.py
|- payloads.py
|- runtime.py
|- serve.py
|- storage.py
|- web.py
`- __main__.py
```

## Entry points

- `kg`
- `knowledge-graph`
- `python -m knowledge_graph`
- `python -m knowledge_graph.server`
- `python -m knowledge_graph.mcp.server`
- `knowledge-graph web`

## MCP setup

### Claude Code

Claude Code uses the `.mcp.json` approach. A minimal configuration looks like this:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "D:/anaconda3/Scripts/knowledge-graph.exe",
      "args": [
        "serve"
      ],
      "env": {
        "PYTHONPATH": "E:/Education/mcp_server/knowledge-graph/src"
      }
    }
  }
}
```

### Codex

Codex uses the `~/.codex/config.toml` approach. The current setup for this repository looks like this:

```toml
[mcp_servers.knowledge-graph]
command = "D:/anaconda3/Scripts/knowledge-graph.exe"
args = ["serve"]

[mcp_servers.knowledge-graph.env]
PYTHONPATH = "E:/Education/mcp_server/knowledge-graph/src"
```

This Codex example intentionally omits `cwd`. With the current runtime model, that lets `.graph_db` follow the inherited launch directory of the MCP process instead of forcing a fixed repo path.

If you want per-tool approvals in Codex, extend that block with tool-specific settings in the same file.

## Web app

Start the persistent app with:

```bash
knowledge-graph web --host 127.0.0.1 --port 5000
```

The app exposes:

- `POST /api/build`
- `GET /api/builds/{job_id}`
- `GET /api/repo_info`
- `GET /api/graph_entities`
- `GET /api/file_details`
- `POST /api/auto_complete`
- `POST /api/get_neighbors`
- `POST /api/find_paths`
- `POST /api/chat`

The browser UI is query-driven. It does not depend on a generated `index.html + graph.json` bundle.

When an MCP `build_or_update_graph` call starts, the web app is also made available in parallel and the response includes `web_url`, `api_url`, and `build_status_url` so the same build can be watched live in the browser.

## MCP tools

The MCP surface includes:

- `build_or_update_graph`
- `get_build_status`
- `cancel_build`
- `stop_web_server`
- `autocomplete_entities`
- `get_neighbors`
- `find_paths`
- `ask_graph`
- `trace_dataflow`
- `get_impact_radius`

## Notes

- Runtime outputs are written under `.graph_db/`
- Workspace databases live under `.graph_db/workspaces/<workspace>/graph.sqlite3`
- Background build statuses live under `.graph_db/jobs/<job_id>.json`
- The background web server stays alive until it is stopped explicitly through `stop_web_server` or the hosting MCP process exits
