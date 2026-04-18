"""MCP server entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from code_review_graph_mcp.server import create_server


def run_server(root: Path, db_path: Path) -> None:
    server = create_server(root_path=root, db_path=db_path, name="code-review-graph")
    if hasattr(server, "run"):
        server.run()
        return
    raise RuntimeError("MCP server could not be started.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    db_path = args.db or args.root / ".code-review-graph" / "graph.sqlite3"
    run_server(args.root, db_path)


if __name__ == "__main__":
    main()
