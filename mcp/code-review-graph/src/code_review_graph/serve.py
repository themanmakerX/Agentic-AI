from __future__ import annotations

from pathlib import Path
import sys

from code_review_graph_mcp.server import create_server


def main() -> int:
    root = Path.cwd()
    db_path = root / ".code-review-graph" / "graph.sqlite3"
    server = create_server(root_path=root, db_path=db_path, name="code-review-graph")
    if hasattr(server, "run"):
        server.run()
        return 0
    print("MCP server could not be started.", file=sys.stderr)
    return 1
