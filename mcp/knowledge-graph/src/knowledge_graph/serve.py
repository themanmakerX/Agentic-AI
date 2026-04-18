from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    try:
        from knowledge_graph.mcp.server import create_server
    except ModuleNotFoundError as exc:
        print(
            "MCP server module could not be imported. Ensure the project src directory is on PYTHONPATH.",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 1

    root = Path.cwd()
    db_path = Path(".graph_db").resolve() / "graph.sqlite3"
    server = create_server(root_path=root, db_path=db_path, name="knowledge-graph")
    if hasattr(server, "run"):
        server.run()
        return 0
    print("MCP server could not be started.", file=sys.stderr)
    return 1


