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
- an installed `knowledge-graph` launcher, for example:

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

## Core capabilities

- persistent graph builds for a workspace
- incremental graph refreshes
- graph neighborhood expansion
- path discovery and structural tracing
- impact-radius and review-context generation
- retrieval-backed graph Q&A
- workspace auditing and architecture summaries
- lightweight wiki generation and refactor suggestions
- a web UI for live graph browsing and build monitoring

## MCP setup

### Claude Code

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "D:/anaconda3/Scripts/knowledge-graph.exe",
      "args": ["serve"],
      "env": {
        "PYTHONPATH": "E:/Education/mcp_server/knowledge-graph/src"
      }
    }
  }
}
```

### Codex

```toml
[mcp_servers.knowledge-graph]
command = "D:/anaconda3/Scripts/knowledge-graph.exe"
args = ["serve"]

[mcp_servers.knowledge-graph.env]
PYTHONPATH = "E:/Education/mcp_server/knowledge-graph/src"
```

This Codex example intentionally omits `cwd`, so `.graph_db` follows the inherited launch directory of the MCP process.

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

When an MCP `build_or_update_graph` call starts, the web app can also be made available in parallel and returns `web_url`, `api_url`, and `build_status_url`.

## MCP tools

The current MCP surface includes:

- `build_or_update_graph`
- `get_build_status`
- `cancel_build`
- `stop_web_server`
- `autocomplete_entities`
- `get_neighbors`
- `get_impact_radius`
- `get_review_context`
- `query_graph`
- `semantic_search_nodes`
- `list_graph_stats`
- `find_files_by_pattern`
- `detect_changes`
- `find_paths`
- `trace_dataflow`
- `ask_graph`
- `audit_workspace`
- `list_communities`
- `get_architecture_overview`
- `refactor_workspace`
- `generate_wiki`

## Runtime notes

- runtime outputs are written under `.graph_db/`
- workspace databases live under `.graph_db/workspaces/<workspace>/graph.sqlite3`
- background build statuses live under `.graph_db/jobs/<job_id>.json`
- the background web server stays alive until explicitly stopped or the hosting MCP process exits
